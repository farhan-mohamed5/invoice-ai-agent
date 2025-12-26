import json
from typing import List, Optional
from sqlalchemy.orm import Session

from apps.api.models.invoice_model import Invoice
from apps.api.schemas.invoice_schema import InvoiceUpdate

# Import LLM functions from worker 
from apps.worker.pipeline.services_ocr_llm import (
    InvoiceExtraction,
    resolve_review_with_llm,
)

# Import Google Sheets sync
from apps.worker.pipeline.storage import update_invoice_in_sheet


class InvoiceService:
    """
    Thin data-access layer for invoices.

    Creation and OCR are handled by the worker.
    This service supports reads, manual updates, and review resolution.
    """

    # ------------------------------------------------------------
    # Fetch all invoices
    # ------------------------------------------------------------
    def get_all_invoices(self, db: Session):
        return db.query(Invoice).order_by(Invoice.id.desc()).all()

    # ------------------------------------------------------------
    # Fetch single invoice by ID
    # ------------------------------------------------------------
    def get_invoice(self, db: Session, invoice_id: int) -> Optional[Invoice]:
        return db.query(Invoice).filter(Invoice.id == invoice_id).first()

    # ------------------------------------------------------------
    # Manual update with Google Sheets sync
    # ------------------------------------------------------------
    def update_invoice(
        self,
        db: Session,
        invoice_id: int,
        payload: InvoiceUpdate,
    ) -> Optional[Invoice]:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            return None

        updates = payload.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(invoice, field, value)

        db.commit()
        db.refresh(invoice)
        
        # Sync to Google Sheets after update
        try:
            invoice_dict = {
                "id": invoice.id,
                "import_timestamp": invoice.created_at.strftime("%Y-%m-%d %H:%M:%S") if invoice.created_at else "",
                "file_original_name": invoice.file_original_name,
                "file_new_path": invoice.file_new_path,
                "source": invoice.source,
                "date": invoice.date,
                "vendor": invoice.vendor,
                "amount": invoice.amount,
                "currency": invoice.currency or "AED",
                "tax_amount": invoice.tax_amount,
                "category": invoice.category,
                "payment_method": invoice.payment_method,
                "transaction_type": invoice.transaction_type,
                "is_paid": invoice.is_paid,
                "ocr_confidence": invoice.ocr_confidence,
                "extraction_confidence": invoice.extraction_confidence,
                "status": invoice.status,
                "notes": invoice.notes,
                "reviewed_at": invoice.updated_at.strftime("%Y-%m-%d %H:%M:%S") if invoice.updated_at else "",
                "email_from": None,
                "email_subject": None,
                "email_message_id": None,
            }
            update_invoice_in_sheet(invoice_dict)
        except Exception as e:
            print(f"Warning: Could not sync to Google Sheets: {e}")
        
        return invoice

    # ------------------------------------------------------------
    # Resolve needs_review by applying user answers
    # ------------------------------------------------------------
    def resolve_review(
        self,
        db: Session,
        invoice_id: int,
        questions: List[dict],
        answers: dict,
    ) -> Optional[Invoice]:
        """
        Resolve a needs_review invoice using user-provided answers.
        
        Applies user answers directly to the invoice fields.
        
        Args:
            db: Database session
            invoice_id: The invoice to resolve
            questions: The original review questions (from DB)
            answers: User's answers { field_name: value }
        
        Returns:
            Updated Invoice or None if not found
        """
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            return None

        # Apply each answer to the corresponding field
        for field_name, value in answers.items():
            if value is None:
                continue
                
            if field_name == "amount":
                invoice.amount = float(value) if value else None
            elif field_name == "date":
                invoice.date = str(value) if value else None
            elif field_name == "vendor":
                invoice.vendor = str(value) if value else None
            elif field_name == "tax_amount":
                invoice.tax_amount = float(value) if value else None
            elif field_name == "category":
                invoice.category = str(value) if value else None
            elif field_name == "payment_method":
                invoice.payment_method = str(value) if value else None
            elif field_name == "is_paid":
                # Handle various formats: bool, string "true"/"false", etc.
                if isinstance(value, bool):
                    invoice.is_paid = 1 if value else 0
                elif isinstance(value, str):
                    invoice.is_paid = 1 if value.lower() in ("true", "yes", "1") else 0
                else:
                    invoice.is_paid = 1 if value else 0
            elif field_name == "currency":
                invoice.currency = str(value) if value else "AED"
            elif field_name == "transaction_type":
                invoice.transaction_type = str(value) if value else None

        # Update confidence (user-verified = high confidence)
        invoice.extraction_confidence = 0.95

        # Clear review state
        invoice.status = "ok"
        invoice.review_questions = None
        invoice.review_reason = None

        db.commit()
        db.refresh(invoice)
        
        # Sync to Google Sheets
        try:
            invoice_dict = {
                "id": invoice.id,
                "import_timestamp": invoice.created_at.strftime("%Y-%m-%d %H:%M:%S") if invoice.created_at else "",
                "file_original_name": invoice.file_original_name,
                "file_new_path": invoice.file_new_path,
                "source": invoice.source,
                "date": invoice.date,
                "vendor": invoice.vendor,
                "amount": invoice.amount,
                "currency": invoice.currency or "AED",
                "tax_amount": invoice.tax_amount,
                "category": invoice.category,
                "payment_method": invoice.payment_method,
                "transaction_type": invoice.transaction_type,
                "is_paid": invoice.is_paid,
                "ocr_confidence": invoice.ocr_confidence,
                "extraction_confidence": invoice.extraction_confidence,
                "status": invoice.status,
                "notes": invoice.notes,
                "reviewed_at": invoice.updated_at.strftime("%Y-%m-%d %H:%M:%S") if invoice.updated_at else "",
                "email_from": None,
                "email_subject": None,
                "email_message_id": None,
            }
            update_invoice_in_sheet(invoice_dict)
        except Exception as e:
            print(f"Warning: Could not sync to Google Sheets: {e}")
        
        return invoice

    # ------------------------------------------------------------
    # Bulk fetch invoices needing review (useful for dashboard)
    # ------------------------------------------------------------
    def get_invoices_needing_review(self, db: Session) -> List[Invoice]:
        return (
            db.query(Invoice)
            .filter(Invoice.status == "needs_review")
            .order_by(Invoice.id.desc())
            .all()
        )

    # ------------------------------------------------------------
    # Mark invoice as manually reviewed 
    # ------------------------------------------------------------
    def mark_as_reviewed(
        self,
        db: Session,
        invoice_id: int,
        notes: Optional[str] = None,
    ) -> Optional[Invoice]:
        """
        Manually mark an invoice as reviewed without LLM.
        Useful when user just wants to approve as-is.
        """
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            return None

        invoice.status = "ok"
        invoice.review_questions = None
        invoice.review_reason = None
        
        if notes:
            existing_notes = invoice.notes or ""
            invoice.notes = f"{existing_notes}\n[Manually reviewed] {notes}".strip()

        db.commit()
        db.refresh(invoice)
        
        # Sync to Google Sheets
        try:
            invoice_dict = {
                "id": invoice.id,
                "import_timestamp": invoice.created_at.strftime("%Y-%m-%d %H:%M:%S") if invoice.created_at else "",
                "file_original_name": invoice.file_original_name,
                "file_new_path": invoice.file_new_path,
                "source": invoice.source,
                "date": invoice.date,
                "vendor": invoice.vendor,
                "amount": invoice.amount,
                "currency": invoice.currency or "AED",
                "tax_amount": invoice.tax_amount,
                "category": invoice.category,
                "payment_method": invoice.payment_method,
                "transaction_type": invoice.transaction_type,
                "is_paid": invoice.is_paid,
                "ocr_confidence": invoice.ocr_confidence,
                "extraction_confidence": invoice.extraction_confidence,
                "status": invoice.status,
                "notes": invoice.notes,
                "reviewed_at": invoice.updated_at.strftime("%Y-%m-%d %H:%M:%S") if invoice.updated_at else "",
                "email_from": None,
                "email_subject": None,
                "email_message_id": None,
            }
            update_invoice_in_sheet(invoice_dict)
        except Exception as e:
            print(f"Warning: Could not sync to Google Sheets: {e}")
        
        return invoice


invoice_service = InvoiceService()
