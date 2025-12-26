from __future__ import annotations
from pathlib import Path
from textwrap import shorten
from typing import Dict, Any

from apps.worker.pipeline.config import InvoiceStatus, INBOX_DIR, ALLOWED_EXTS
from apps.worker.pipeline.services_ocr_llm import extract_text_with_ocr_if_needed, extract_fields_with_llm
from apps.worker.pipeline.file_organizer import move_invoice_file
from apps.worker.pipeline.storage import init_db, insert_invoice, fetch_all_invoices, append_invoice_to_sheet


def process_single_invoice(path: Path, source: str = "local") -> Dict[str, Any]:
    """
    End-to-end processing of one invoice:
      1. OCR / text extraction (if needed)
      2. LLM field extraction
      3. Insert row into SQLite
      4. Move file into organized folder
      5. Append to Google Sheet (if configured)
    Returns a dict with DB row values (minus id).
    """
    # Step 1: OCR / text
    text, text_source = extract_text_with_ocr_if_needed(path)
    
    # Step 2: LLM extraction
    llm_result = extract_fields_with_llm(text)
    
    # Step 3: move file based on extracted metadata
    new_path = move_invoice_file(
        original_path=path,
        vendor=llm_result.vendor,
        date=llm_result.date,
        category=llm_result.category,
    )
    
    notes = shorten(text.replace("\n", " "), width=400, placeholder="…")
    
    status = (
        llm_result.status.value
        if isinstance(llm_result.status, InvoiceStatus)
        else str(llm_result.status)
    )
    
    # Step 4: insert DB row (NOW WITH transaction_type and is_paid!)
    row_id = insert_invoice(
        file_original_name=path.name,
        file_new_path=str(new_path),
        date=llm_result.date,
        vendor=llm_result.vendor,
        amount=llm_result.amount,
        currency=llm_result.currency,
        tax_amount=llm_result.tax_amount,
        category=llm_result.category,
        payment_method=llm_result.payment_method,
        transaction_type=llm_result.transaction_type,
        is_paid=llm_result.is_paid,
        source=source,
        ocr_confidence=llm_result.ocr_confidence,
        extraction_confidence=llm_result.extraction_confidence,
        status=status,
        notes=notes,
    )
    
    # Step 5: fetch the full row to push to sheets
    df = fetch_all_invoices()
    db_row = df[df["id"] == row_id].to_dict(orient="records")[0]
    append_invoice_to_sheet(db_row)
    
    return db_row


def process_inbox_once() -> None:
    """
    Scan INBOX_DIR once and process all supported files.
    """
    for path in sorted(INBOX_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_EXTS:
            continue
        
        print(f"[INBOX] Processing {path.name} …")
        try:
            process_single_invoice(path, source="local")
            print(f"[OK] Processed {path.name}")
        except Exception as exc:
            print(f"[ERROR] Failed to process {path.name}: {exc!r}")


def bootstrap() -> None:
    """Initialize DB and folders."""
    init_db()
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
