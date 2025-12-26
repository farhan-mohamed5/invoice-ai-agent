import json
from datetime import date, datetime
from typing import Any, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.core.db import get_db
from apps.api.models.invoice_model import Invoice
from apps.api.schemas.invoice_schema import (
    InvoiceOut,
    InvoiceUpdate,
    ResolveReviewRequest,
    ResolveReviewResponse,
    ReviewQuestion,
)
from apps.api.services.invoice_service import invoice_service

router = APIRouter()

DEFAULT_VAT_RATE = 0.05  # UAE default

ALLOWED_ANSWER_FIELDS = {
    "vendor",
    "date",
    "amount",
    "currency",
    "tax_amount",
    "category",
    "payment_method",
    "transaction_type",
    "is_paid",
    "notes",
    "vat_inclusive",
}


def _to_jsonable_questions(questions: Any) -> list[dict]:
    out: list[dict] = []
    if not questions:
        return out
    for q in questions:
        if isinstance(q, dict):
            out.append(q)
        elif hasattr(q, "model_dump"):  # pydantic v2
            out.append(q.model_dump())
        elif hasattr(q, "dict"):  # pydantic v1
            out.append(q.dict())
    return out


def _extract_field_names(questions: list[dict]) -> set[str]:
    fields: set[str] = set()
    for q in questions or []:
        if isinstance(q, dict):
            fn = q.get("field_name")
            if fn:
                fields.add(str(fn))
    return fields


def _get_or_build_review_questions(
    invoice: Invoice, db: Session
) -> Tuple[list[dict], str | None]:
    """
    Ensures review questions are persisted in DB for needs_review invoices.
    Returns (questions_as_dicts, reason).
    """
    if invoice.review_questions:
        try:
            stored = json.loads(invoice.review_questions)
            if isinstance(stored, list) and stored:
                return stored, invoice.review_reason
        except (json.JSONDecodeError, TypeError):
            pass

    if invoice.status != "needs_review":
        return [], invoice.review_reason

    from apps.worker.pipeline.services_ocr_llm import (
        InvoiceExtraction,
        build_review_questions,
    )

    extraction = InvoiceExtraction(
        vendor=invoice.vendor,
        date=invoice.date,
        amount=invoice.amount,
        currency=invoice.currency,
        tax_amount=invoice.tax_amount,
        category=invoice.category,
        payment_method=invoice.payment_method,
        transaction_type=invoice.transaction_type,
        is_paid=invoice.is_paid,
        ocr_confidence=invoice.ocr_confidence,
        extraction_confidence=invoice.extraction_confidence,
    )

    questions, reason = build_review_questions(extraction)
    questions_dicts = _to_jsonable_questions(questions)

    invoice.review_questions = json.dumps(questions_dicts) if questions_dicts else None
    invoice.review_reason = reason
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return questions_dicts, reason


def _invoice_to_out(invoice: Invoice) -> InvoiceOut:
    review_questions = None
    if invoice.review_questions:
        try:
            raw = json.loads(invoice.review_questions)
            review_questions = [ReviewQuestion(**q) for q in raw]
        except (json.JSONDecodeError, TypeError):
            review_questions = None

    return InvoiceOut(
        id=invoice.id,
        file_original_name=invoice.file_original_name,
        file_new_path=invoice.file_new_path,
        date=invoice.date,
        vendor=invoice.vendor,
        amount=invoice.amount,
        currency=invoice.currency,
        tax_amount=invoice.tax_amount,
        category=invoice.category,
        payment_method=invoice.payment_method,
        transaction_type=invoice.transaction_type,
        is_paid=bool(invoice.is_paid) if invoice.is_paid is not None else None,
        source=invoice.source,
        ocr_confidence=invoice.ocr_confidence,
        extraction_confidence=invoice.extraction_confidence,
        status=invoice.status,
        notes=invoice.notes,
        company_id=invoice.company_id,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        review_reason=invoice.review_reason,
        review_questions=review_questions,
    )


def _coerce_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes", "y"}:
            return True
        if s in {"false", "0", "no", "n"}:
            return False
    return None


def _normalize_vat(answers: dict) -> dict:
    """
    VAT rules (no VAT rate input):
    - vat_inclusive = True  -> amount is GROSS. If tax_amount missing, compute VAT portion at 5% from gross.
    - vat_inclusive = False -> amount is NET. tax_amount used if provided else computed at 5%.
                              stored amount becomes GROSS, tax_amount stored.
    """
    out = dict(answers or {})

    vat_inclusive = _coerce_bool(out.get("vat_inclusive"))
    if "vat_inclusive" in out and vat_inclusive is None:
        raise HTTPException(status_code=400, detail="vat_inclusive must be a boolean")

    if vat_inclusive is None:
        return out

    # If no amount, can't normalize totals; still allow tax_amount to save.
    if out.get("amount") is None:
        out["vat_inclusive"] = vat_inclusive
        return out

    try:
        entered_amount = float(out["amount"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="amount must be a number")

    tax_amount = out.get("tax_amount")
    if tax_amount is not None and tax_amount != "":
        try:
            tax_amount = float(tax_amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="tax_amount must be a number")
    else:
        tax_amount = None

    if vat_inclusive is True:
        gross = entered_amount
        if tax_amount is None:
            tax_amount = gross - (gross / (1.0 + DEFAULT_VAT_RATE))  # VAT portion inside gross
        out["amount"] = round(gross, 2)
        out["tax_amount"] = round(tax_amount, 2) if tax_amount is not None else None
        out["vat_inclusive"] = True
        return out

    # vat_inclusive is False: entered is NET
    if tax_amount is None:
        tax_amount = entered_amount * DEFAULT_VAT_RATE

    out["amount"] = round(entered_amount, 2)  
    out["tax_amount"] = round(tax_amount, 2)
    out["vat_inclusive"] = False
    return out


def _parse_invoice_date(d: Any) -> date | None:
    if d is None:
        return None
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        s = d.strip()
        if not s:
            return None
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


@router.get("/insights/vat")
def vat_insight(year: int | None = None, db: Session = Depends(get_db)):
    y = year or datetime.utcnow().year
    start = date(y, 1, 1)
    end = date(y + 1, 1, 1)

    invoices = db.query(Invoice).all()

    vat_total = 0.0
    invoice_count = 0
    invoices_with_vat_count = 0
    missing_vat_count = 0
    estimated_missing_vat_total = 0.0

    for inv in invoices:
        inv_date = _parse_invoice_date(inv.date)
        if inv_date is None:
            continue
        if not (start <= inv_date < end):
            continue

        invoice_count += 1

        if inv.tax_amount is not None:
            try:
                vat_total += float(inv.tax_amount)
                invoices_with_vat_count += 1
            except (TypeError, ValueError):
                pass

        if (inv.tax_amount is None or inv.tax_amount == "") and inv.amount is not None:
            try:
                gross = float(inv.amount)
                est_vat = gross - (gross / (1.0 + DEFAULT_VAT_RATE))
                estimated_missing_vat_total += est_vat
                missing_vat_count += 1
            except (TypeError, ValueError):
                pass

    return {
        "year": y,
        "vat_total": round(vat_total, 2),
        "invoice_count": invoice_count,
        "invoices_with_vat_count": invoices_with_vat_count,
        "missing_vat_count": missing_vat_count,
        "estimated_missing_vat_total": round(estimated_missing_vat_total, 2),
        "currency": "AED",
        "assumptions": {
            "vat_rate_assumed": DEFAULT_VAT_RATE,
            "missing_vat_estimation": "Assumes amount is VAT-inclusive when VAT is missing.",
        },
    }


@router.get("/", response_model=list[InvoiceOut])
def list_invoices(db: Session = Depends(get_db)):
    invoices = invoice_service.get_all_invoices(db)
    return [_invoice_to_out(i) for i in invoices]


@router.get("/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    questions, reason = _get_or_build_review_questions(invoice, db)

    return {
        "id": invoice.id,
        "vendor": invoice.vendor,
        "amount": invoice.amount,
        "date": invoice.date,
        "currency": invoice.currency,
        "tax_amount": invoice.tax_amount,
        "category": invoice.category,
        "payment_method": invoice.payment_method,
        "transaction_type": invoice.transaction_type,
        "is_paid": invoice.is_paid,
        "ocr_confidence": invoice.ocr_confidence,
        "extraction_confidence": invoice.extraction_confidence,
        "status": invoice.status,
        "notes": invoice.notes,
        "file_original_name": invoice.file_original_name,
        "file_new_path": invoice.file_new_path,
        "review_questions": questions,
        "review_reason": reason,
    }


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: int, payload: InvoiceUpdate, db: Session = Depends(get_db)):
    invoice = invoice_service.update_invoice(db, invoice_id, payload)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_to_out(invoice)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    db.delete(invoice)
    db.commit()
    return


@router.post("/{invoice_id}/resolve-review", response_model=ResolveReviewResponse)
def resolve_review(invoice_id: int, payload: ResolveReviewRequest, db: Session = Depends(get_db)):
    invoice = invoice_service.get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != "needs_review":
        raise HTTPException(
            status_code=400,
            detail=f"Invoice status is '{invoice.status}', not 'needs_review'. Nothing to resolve.",
        )

    existing_questions, _ = _get_or_build_review_questions(invoice, db)

    answers = dict(payload.answers or {})

    if answers:
        answers = _normalize_vat(answers)

        # FIX: allow VAT + other editable fields even if not present in review_questions
        if existing_questions:
            valid_fields = _extract_field_names(existing_questions)
            valid_fields |= set(ALLOWED_ANSWER_FIELDS)  # <- this includes tax_amount
        else:
            valid_fields = set(ALLOWED_ANSWER_FIELDS)

        invalid = set(answers.keys()) - valid_fields
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid fields: {invalid}. Valid fields are: {valid_fields}",
            )

        for k, v in answers.items():
            if k == "vat_inclusive":
                continue
            if hasattr(invoice, k):
                setattr(invoice, k, v)

    invoice.status = "ok"
    invoice.review_questions = None
    invoice.review_reason = None

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return ResolveReviewResponse(
        success=True,
        message="Invoice updated successfully. Status is now 'ok'.",
        invoice=_invoice_to_out(invoice),
    )


@router.get("/{invoice_id}/review-questions", response_model=list[ReviewQuestion])
def get_review_questions(invoice_id: int, db: Session = Depends(get_db)):
    invoice = invoice_service.get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != "needs_review":
        return []

    questions_dicts, _ = _get_or_build_review_questions(invoice, db)
    if not questions_dicts:
        return []

    return [ReviewQuestion(**q) for q in questions_dicts]