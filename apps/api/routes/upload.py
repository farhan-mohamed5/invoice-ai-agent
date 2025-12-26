from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Any

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from apps.api.core.db import get_db, SessionLocal  # SessionLocal must exist in apps/api/core/db.py
from apps.api.models.invoice_model import Invoice

router = APIRouter()

# Use separate temp directory for web uploads 
UPLOAD_DIR = Path("invoice_agent_data/temp_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def validate_file(file: UploadFile) -> None:
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )


def _extract_invoice_id(result: Any) -> int | None:
    """
    process_single_invoice() might return:
      - int invoice_id
      - str invoice_id
      - dict containing {"id": ...} or {"invoice_id": ...}
    """
    if result is None:
        return None
    if isinstance(result, bool):
        return None
    if isinstance(result, (int, float)):
        try:
            return int(result)
        except Exception:
            return None
    if isinstance(result, str):
        try:
            return int(result.strip())
        except Exception:
            return None
    if isinstance(result, dict):
        for k in ("id", "invoice_id"):
            if k in result and result[k] is not None:
                try:
                    return int(result[k])
                except Exception:
                    return None
    return None


def _copy_processed_into_placeholder(db: Session, *, placeholder_id: int, processed_id: int) -> None:
    """
    Copies the processed invoice fields onto the placeholder invoice row,
    then deletes the processed row to avoid duplicates.
    """
    placeholder = db.query(Invoice).filter(Invoice.id == placeholder_id).first()
    if not placeholder:
        raise RuntimeError(f"Placeholder invoice not found: {placeholder_id}")

    processed = db.query(Invoice).filter(Invoice.id == processed_id).first()
    if not processed:
        raise RuntimeError(f"Processed invoice not found: {processed_id}")

    # If pipeline somehow updated the same row, just mark updated_at + return
    if processed.id == placeholder.id:
        placeholder.updated_at = datetime.utcnow()
        db.add(placeholder)
        db.commit()
        return

    skip = {"id", "created_at", "updated_at"}
    for col in Invoice.__table__.columns:
        name = col.name
        if name in skip:
            continue
        setattr(placeholder, name, getattr(processed, name))

    # Ensure placeholder reflects latest
    placeholder.updated_at = datetime.utcnow()

    # Delete processed row to avoid duplicate invoice entries
    db.delete(processed)
    db.add(placeholder)
    db.commit()


def process_invoice_in_background(file_path: Path, original_filename: str, placeholder_id: int) -> None:
    """
    Background task:
      - run pipeline
      - find processed_id safely
      - merge processed row into placeholder row
      - mark placeholder as error if failure
      - cleanup temp file
    """
    try:
        from apps.worker.pipeline.core_pipeline import process_single_invoice

        print(f"[UPLOAD] Processing {original_filename} (placeholder #{placeholder_id})...")

        result = process_single_invoice(file_path, source="upload")
        processed_id = _extract_invoice_id(result)

        if processed_id is None:
            raise RuntimeError(
                f"process_single_invoice returned no usable id (type={type(result).__name__})"
            )

        with SessionLocal() as db:
            _copy_processed_into_placeholder(
                db,
                placeholder_id=int(placeholder_id),
                processed_id=int(processed_id),
            )

        print(
            f"[UPLOAD] Done {original_filename}: processed #{processed_id} -> merged into placeholder #{placeholder_id}"
        )

    except Exception as e:
        print(f"[UPLOAD] Error processing {original_filename}: {e}")
        import traceback

        traceback.print_exc()

        # Best-effort: mark placeholder as error
        try:
            with SessionLocal() as db:
                inv = db.query(Invoice).filter(Invoice.id == int(placeholder_id)).first()
                if inv:
                    inv.status = "error"
                    inv.notes = f"Processing error: {e}"
                    inv.updated_at = datetime.utcnow()
                    db.add(inv)
                    db.commit()
        except Exception:
            pass

    finally:
        # Cleanup temp upload file
        try:
            if file_path.exists():
                file_path.unlink()
                print(f"[UPLOAD] Cleaned up temp file: {file_path}")
        except Exception as e:
            print(f"[UPLOAD] Could not delete temp file {file_path}: {e}")


@router.post("/")
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload one or more invoice files.

    Creates a placeholder invoice row immediately with status='processing'
    so the UI can show it right away.
    Then a background task processes the file and updates that same row.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results = []

    for file in files:
        try:
            validate_file(file)

            # Read file content
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{file.filename}' exceeds maximum size of 20MB",
                )

            # Save temp file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            original_name = Path(file.filename).stem
            ext = Path(file.filename).suffix.lower()
            unique_name = f"{original_name}_{timestamp}{ext}"
            file_path = UPLOAD_DIR / unique_name

            with open(file_path, "wb") as buffer:
                buffer.write(content)

            print(f"[UPLOAD] Saved {file.filename} to temp: {file_path}")

            # Create placeholder invoice immediately
            placeholder = Invoice(
                import_timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                file_original_name=file.filename,
                file_new_path=str(file_path),  # temporary path until processed result is merged
                source="upload",
                status="processing",
                notes="Processing…",
            )
            db.add(placeholder)
            db.commit()
            db.refresh(placeholder)

            # Background processing (no db session passed)
            background_tasks.add_task(
                process_invoice_in_background,
                file_path,
                file.filename,
                int(placeholder.id),
            )

            results.append(
                {
                    "filename": file.filename,
                    "status": "uploaded",
                    "message": "File uploaded and processing started",
                    "invoice_id": placeholder.id,  # ✅ UI can use this immediately
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            results.append(
                {
                    "filename": getattr(file, "filename", "unknown"),
                    "status": "error",
                    "message": str(e),
                }
            )

    successes = sum(1 for r in results if r["status"] == "uploaded")
    failures = len(results) - successes

    return JSONResponse(
        status_code=200 if failures == 0 else 207,
        content={
            "message": f"Uploaded {successes} file(s)" + (f", {failures} failed" if failures else ""),
            "results": results,
        },
    )


@router.get("/status/{invoice_id}")
async def get_upload_status(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return {
        "id": invoice.id,
        "filename": invoice.file_original_name,
        "status": invoice.status,
        "vendor": invoice.vendor,
        "amount": invoice.amount,
        "date": invoice.date,
        "notes": invoice.notes,
    }