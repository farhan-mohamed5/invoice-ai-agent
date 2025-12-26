from celery import shared_task
from apps.worker.celery_app import app
from apps.worker.pipeline.storage import sync_from_sheets_to_db


@app.task(name="sync_sheets_to_db_task")
def sync_sheets_to_db_task():
    """
    Periodic Celery task to sync edits from Google Sheets back to database.
    
    Runs every 5 minutes (configured in celery_app.py beat_schedule).
    
    Only syncs EDITABLE fields:
    - vendor, tax_amount, category, payment_method, is_paid, transaction_type, notes
    
    Protected fields never sync from Sheets:
    - amount, date, id, file paths, timestamps
    """
    try:
        print("[SYNC TASK] Starting Google Sheets → DB sync...")
        result = sync_from_sheets_to_db()
        print(f"[SYNC TASK] Completed: {result}")
        return result
    except Exception as e:
        print(f"[SYNC TASK] Error: {e}")
        return {
            "status": "error",
            "reason": str(e),
            "updated": 0,
            "errors": 1
        }