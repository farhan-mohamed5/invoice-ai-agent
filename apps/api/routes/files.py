from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter()

@router.get("/files/{invoice_id}")
def get_invoice_file(invoice_id: int):
    from apps.api.core.db import SessionLocal
    from apps.api.models.invoice_model import Invoice

    db = SessionLocal()
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    db.close()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    file_path = invoice.file_new_path

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(path=file_path, filename=os.path.basename(file_path))