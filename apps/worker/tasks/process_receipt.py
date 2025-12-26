from celery import shared_task
import traceback

from apps.worker.celery_app import app
from apps.worker.pipeline.core_pipeline import process_file

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.core.db import DATABASE_URL
from apps.api.models.invoice_model import Receipt


# Create DB engine for the worker
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine)


@app.task(name="process_receipt_task")
def process_receipt_task(file_path: str):
    """
    Worker execution of the OCR + LLM + categorization pipeline.
    """

    session = SessionLocal()

    try:
        print(f"[WORKER] Processing file: {file_path}")

        # CALL  EXISTING PIPELINE
        result = process_file(file_path)

        # Pipeline returns parsed fields → update DB
        receipt = (
            session.query(Receipt)
            .filter(Receipt.file_new_path == file_path)
            .first()
        )

        if receipt:
            if result.get("vendor"):
                receipt.vendor = result["vendor"]

            if result.get("amount"):
                receipt.amount = result["amount"]

            if result.get("currency"):
                receipt.currency = result["currency"]

            if result.get("category"):
                receipt.category = result["category"]

            if result.get("payment_method"):
                receipt.payment_method = result["payment_method"]

            receipt.ocr_confidence = result.get("ocr_confidence")
            receipt.extraction_confidence = result.get("extraction_confidence")
            receipt.notes = result.get("notes", "")
            receipt.status = "ok"

            session.commit()
            print(f"[WORKER] Updated receipt #{receipt.id}")

        else:
            print("[WORKER] WARNING: No matching DB row found for this file.")

        return {"status": "done", "file": file_path}

    except Exception as e:
        print("[WORKER] ERROR:", e)
        print(traceback.format_exc())
        return {"status": "error", "file": file_path, "error": str(e)}

    finally:
        session.close()