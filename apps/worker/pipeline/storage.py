from __future__ import annotations

import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Dict, Optional

import pandas as pd  # type: ignore

from apps.worker.pipeline.config import (
    DB_PATH,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_WORKSHEET,
)

try:
    import gspread  # type: ignore
except ImportError:  # pragma: no cover
    gspread = None  # type: ignore


# -------------------------------------------------
# Feature flags / helpers
# -------------------------------------------------

def _sheets_enabled() -> bool:
    """
    Sheets sync OFF by default.
    Enable with: INVOICE_AGENT_SHEETS_ENABLED=1
    """
    return os.getenv("INVOICE_AGENT_SHEETS_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


def _safe_sheet_value(v: Any) -> Any:
    """
    Google API rejects NaN/Inf floats inside JSON.
    Convert them to empty strings so appends/updates never crash.

    Also normalize date/datetime into ISO strings.
    """
    if v is None:
        return ""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return ""
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return v


# -------------------------------------------------
# SQLite helpers
# -------------------------------------------------

def init_db() -> None:
    """Create invoices table if it does not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_timestamp TEXT,
                file_original_name TEXT,
                file_new_path TEXT,
                source TEXT,
                date TEXT,
                vendor TEXT,
                amount REAL,
                currency TEXT,
                tax_amount REAL,
                category TEXT,
                payment_method TEXT,
                transaction_type TEXT,
                is_paid INTEGER,
                ocr_confidence REAL,
                extraction_confidence REAL,
                status TEXT,
                notes TEXT,
                reviewed_at TEXT,
                email_from TEXT,
                email_subject TEXT,
                email_message_id TEXT
            );
            """
        )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def insert_invoice(
    *,
    file_original_name: str,
    file_new_path: str,
    date: Optional[str],
    vendor: Optional[str],
    amount: Optional[float],
    currency: Optional[str],
    tax_amount: Optional[float],
    category: Optional[str],
    payment_method: Optional[str],
    transaction_type: Optional[str],
    is_paid: Optional[bool],
    source: str,
    ocr_confidence: Optional[float],
    extraction_confidence: Optional[float],
    status: str,
    notes: str,
) -> int:
    """Insert one row and return its ID."""
    import_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO invoices (
                import_timestamp,
                file_original_name,
                file_new_path,
                source,
                date,
                vendor,
                amount,
                currency,
                tax_amount,
                category,
                payment_method,
                transaction_type,
                is_paid,
                ocr_confidence,
                extraction_confidence,
                status,
                notes,
                reviewed_at,
                email_from,
                email_subject,
                email_message_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_ts,
                file_original_name,
                file_new_path,
                source,
                date,
                vendor,
                amount,
                currency,
                tax_amount,
                category,
                payment_method,
                transaction_type,
                1 if is_paid is True else 0 if is_paid is False else None,
                ocr_confidence,
                extraction_confidence,
                status,
                notes,
                None,  # reviewed_at
                None,  # email_from
                None,  # email_subject
                None,  # email_message_id
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def update_invoice_payment_status(invoice_id: int, is_paid: bool) -> None:
    """Update the payment status of an invoice."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE invoices
            SET is_paid = ?
            WHERE id = ?
            """,
            (1 if is_paid else 0, invoice_id),
        )
        conn.commit()


def fetch_all_invoices() -> pd.DataFrame:
    """Return all invoices as a DataFrame for dashboard."""
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM invoices ORDER BY id DESC", conn)
    return df


def fetch_all_invoices_dict() -> list[dict]:
    """Return all invoices as list of dictionaries for API usage."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices ORDER BY id DESC")
        rows = cur.fetchall()
        columns = [col[0] for col in cur.description]
        return [dict(zip(columns, row)) for row in rows]


def fetch_invoice_by_id(invoice_id: int) -> Optional[dict]:
    """Return a single invoice by ID as a dictionary."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
        return dict(zip(columns, row))


def compute_summary() -> dict:
    """Compute KPI summary for the dashboard."""
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT SUM(amount)
            FROM invoices
            WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
            """
        )
        total_spend = cur.fetchone()[0] or 0

        cur.execute(
            """
            SELECT COUNT(*)
            FROM invoices
            WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
            """
        )
        invoices_month = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM invoices
            WHERE status = 'needs_review'
            """
        )
        needs_review = cur.fetchone()[0]

        cur.execute(
            """
            SELECT category, SUM(amount)
            FROM invoices
            GROUP BY category
            ORDER BY SUM(amount) DESC
            """
        )
        category_rows = cur.fetchall()
        categories = [{"category": r[0], "total": r[1]} for r in category_rows if r[0] is not None]

    return {
        "total_spend_month": total_spend,
        "invoices_month": invoices_month,
        "needs_review": needs_review,
        "categories": categories,
    }


# -------------------------------------------------
# Google Sheets sync 
# -------------------------------------------------

def _get_gspread_sheet():
    if not _sheets_enabled():
        return None
    if GOOGLE_SERVICE_ACCOUNT_FILE is None or GOOGLE_SHEET_ID is None:
        return None
    if gspread is None:
        return None

    sa = gspread.service_account(filename=str(GOOGLE_SERVICE_ACCOUNT_FILE))
    sh = sa.open_by_key(GOOGLE_SHEET_ID)
    return sh.worksheet(GOOGLE_SHEET_WORKSHEET)


def append_invoice_to_sheet(invoice_row: Dict[str, Any]) -> None:
    """
    Append a single invoice row to Google Sheet.
    No-ops if Sheets is disabled or not configured.
    """
    ws = _get_gspread_sheet()
    if ws is None:
        return

    ordered_keys = [
        "id",
        "import_timestamp",
        "file_original_name",
        "file_new_path",
        "source",
        "date",
        "vendor",
        "amount",
        "currency",
        "tax_amount",
        "category",
        "payment_method",
        "transaction_type",
        "is_paid",
        "ocr_confidence",
        "extraction_confidence",
        "status",
        "notes",
        "reviewed_at",
        "email_from",
        "email_subject",
        "email_message_id",
    ]

    row_values = [_safe_sheet_value(invoice_row.get(k, "")) for k in ordered_keys]
    ws.append_row(row_values, value_input_option="USER_ENTERED")


def update_invoice_in_sheet(invoice_row: Dict[str, Any]) -> None:
    """
    Update an existing invoice row in Google Sheet by invoice ID.
    If not found, append it.
    No-ops if Sheets is disabled or not configured.
    """
    ws = _get_gspread_sheet()
    if ws is None:
        return

    invoice_id = invoice_row.get("id")
    if invoice_id is None:
        append_invoice_to_sheet(invoice_row)
        return

    try:
        id_column = ws.col_values(1)  # Column A = IDs
    except Exception:
        append_invoice_to_sheet(invoice_row)
        return

    row_index = None
    for i, cell_value in enumerate(id_column[1:], start=2):
        if str(cell_value).strip() == str(invoice_id):
            row_index = i
            break

    ordered_keys = [
        "id",
        "import_timestamp",
        "file_original_name",
        "file_new_path",
        "source",
        "date",
        "vendor",
        "amount",
        "currency",
        "tax_amount",
        "category",
        "payment_method",
        "transaction_type",
        "is_paid",
        "ocr_confidence",
        "extraction_confidence",
        "status",
        "notes",
        "reviewed_at",
        "email_from",
        "email_subject",
        "email_message_id",
    ]

    row_values = [_safe_sheet_value(invoice_row.get(k, "")) for k in ordered_keys]

    if row_index:
        range_name = f"A{row_index}:V{row_index}"  # 22 columns
        ws.update(values=[row_values], range_name=range_name, value_input_option="USER_ENTERED")
    else:
        ws.append_row(row_values, value_input_option="USER_ENTERED")


def sync_from_sheets_to_db() -> dict:
    """
    Pull edits from Google Sheets back into SQLite.

    No-ops if Sheets is disabled or not configured.
    """
    ws = _get_gspread_sheet()
    if ws is None:
        return {
            "status": "skipped",
            "reason": "Google Sheets not configured or disabled",
            "updated": 0,
            "errors": 0,
        }

    try:
        all_records = ws.get_all_records()
        if not all_records:
            return {"status": "success", "reason": "Sheet is empty", "updated": 0, "errors": 0}

        updated_count = 0
        error_count = 0
        errors: list[str] = []

        with get_conn() as conn:
            cur = conn.cursor()

            for record in all_records:
                invoice_id = record.get("id")
                if not invoice_id:
                    continue

                try:
                    cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
                    db_row = cur.fetchone()
                    if db_row is None:
                        continue

                    columns = [col[0] for col in cur.description]
                    db_invoice = dict(zip(columns, db_row))

                    updates: dict[str, Any] = {}

                    sheet_vendor = (record.get("vendor") or "").strip() or None
                    if sheet_vendor != db_invoice.get("vendor"):
                        updates["vendor"] = sheet_vendor

                    try:
                        raw_tax = record.get("tax_amount")
                        sheet_tax = float(raw_tax) if raw_tax not in (None, "", " ") else None
                        if sheet_tax != db_invoice.get("tax_amount"):
                            updates["tax_amount"] = sheet_tax
                    except (ValueError, TypeError):
                        pass

                    sheet_category = (record.get("category") or "").strip() or None
                    if sheet_category != db_invoice.get("category"):
                        updates["category"] = sheet_category

                    sheet_payment = (record.get("payment_method") or "").strip() or None
                    if sheet_payment != db_invoice.get("payment_method"):
                        updates["payment_method"] = sheet_payment

                    sheet_trans_type = (record.get("transaction_type") or "").strip() or None
                    if sheet_trans_type != db_invoice.get("transaction_type"):
                        updates["transaction_type"] = sheet_trans_type

                    sheet_is_paid = record.get("is_paid")
                    if isinstance(sheet_is_paid, bool):
                        sheet_is_paid_int = 1 if sheet_is_paid else 0
                    elif isinstance(sheet_is_paid, str):
                        sheet_is_paid_int = 1 if sheet_is_paid.lower() in ("true", "yes", "1", "paid") else 0
                    elif isinstance(sheet_is_paid, (int, float)):
                        sheet_is_paid_int = 1 if sheet_is_paid else 0
                    else:
                        sheet_is_paid_int = None

                    if sheet_is_paid_int is not None and sheet_is_paid_int != db_invoice.get("is_paid"):
                        updates["is_paid"] = sheet_is_paid_int

                    sheet_notes = (record.get("notes") or "").strip()
                    db_notes = db_invoice.get("notes") or ""
                    if sheet_notes and sheet_notes != db_notes:
                        updates["notes"] = sheet_notes

                    if updates:
                        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                        values = list(updates.values()) + [invoice_id]
                        cur.execute(f"UPDATE invoices SET {set_clause} WHERE id = ?", values)

                        updated_count += 1
                        print(f"[SHEETS→DB] Updated invoice {invoice_id}: {list(updates.keys())}")

                except Exception as e:
                    error_count += 1
                    errors.append(f"Invoice {invoice_id}: {str(e)}")
                    print(f"[SHEETS→DB] Error updating invoice {invoice_id}: {e}")

            conn.commit()

        return {
            "status": "success" if error_count == 0 else "partial",
            "updated": updated_count,
            "errors": error_count,
            "error_details": errors if errors else None,
        }

    except Exception as e:
        print(f"[SHEETS→DB] Fatal error during sync: {e}")
        return {"status": "error", "reason": str(e), "updated": 0, "errors": 1}


# ---------------------------------------------------------------------------
# Compatibility helpers 
# ---------------------------------------------------------------------------

def _invoice_to_rowdict(invoice: Any) -> Dict[str, Any]:
    """Convert an ORM invoice (or dict) into a plain dict for Sheets helpers."""
    if isinstance(invoice, dict):
        return dict(invoice)

    # Best-effort: pull common attributes if present
    out: Dict[str, Any] = {}
    for key in (
        "id",
        "import_timestamp",
        "file_original_name",
        "file_new_path",
        "source",
        "date",
        "vendor",
        "amount",
        "currency",
        "tax_amount",
        "category",
        "payment_method",
        "transaction_type",
        "is_paid",
        "ocr_confidence",
        "extraction_confidence",
        "status",
        "notes",
        "reviewed_at",
        "email_from",
        "email_subject",
        "email_message_id",
    ):
        if hasattr(invoice, key):
            out[key] = getattr(invoice, key)
    return out


def upsert_invoice_to_sheets(invoice: Any) -> dict:
    """API hook: update-or-append a row in Sheets for this invoice (best-effort)."""
    if not _sheets_enabled():
        return {"status": "skipped", "reason": "Sheets disabled"}

    row = _invoice_to_rowdict(invoice)
    if not row.get("id"):
        return {"status": "skipped", "reason": "Missing invoice id"}

    try:
        # Reuse existing updater (it will append if not found)
        update_invoice_in_sheet(row)
        return {"status": "ok", "action": "upserted", "id": row.get("id")}
    except Exception as e:
        return {"status": "error", "reason": str(e), "id": row.get("id")}


def delete_invoice_from_sheets(invoice_id: int) -> dict:
    """API hook: delete a row in Sheets by invoice id (best-effort)."""
    if not _sheets_enabled():
        return {"status": "skipped", "reason": "Sheets disabled", "id": invoice_id}

    ws = _get_gspread_sheet()
    if ws is None:
        return {
            "status": "skipped",
            "reason": "Google Sheets not configured or disabled",
            "id": invoice_id,
        }

    try:
        headers = ws.row_values(1)
        if not headers:
            return {"status": "skipped", "reason": "Sheet has no header", "id": invoice_id}
        if "id" not in headers:
            # Fallback: assume col A is id
            id_col = 1
        else:
            id_col = headers.index("id") + 1

        ids = ws.col_values(id_col)
        target_row: int | None = None
        for row_idx in range(2, len(ids) + 1):
            if str(ids[row_idx - 1]).strip() == str(invoice_id):
                target_row = row_idx
                break

        if target_row is None:
            return {"status": "skipped", "reason": "Row not found", "id": invoice_id}

        ws.delete_rows(target_row)
        return {"status": "ok", "action": "deleted", "id": invoice_id, "row": target_row}
    except Exception as e:
        return {"status": "error", "reason": str(e), "id": invoice_id}