from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/sheets", tags=["sheets"])


@router.post("/sync-from-sheets")
def trigger_sync_from_sheets():
    """
    Manually trigger sync from Google Sheets to database.
    
    This pulls any edits made in Google Sheets back to the database.
    Useful for testing or immediate sync without waiting for periodic task.
    
    Returns:
        dict: Sync result with count of updated invoices
    """
    try:
        from apps.worker.pipeline.storage import sync_from_sheets_to_db

        result = sync_from_sheets_to_db()
        
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("reason") or "Sync failed")
        
        return {
            "message": "Sync completed",
            "updated_count": (result or {}).get("updated", 0) if isinstance(result, dict) else 0,
            "errors": (result or {}).get("errors", 0) if isinstance(result, dict) else 0,
            "details": result,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync-status")
def get_sync_status():
    """
    Check if Google Sheets sync is configured and working.
    
    Returns:
        dict: Configuration status
    """
    from apps.worker.pipeline.config import (
        GOOGLE_SERVICE_ACCOUNT_FILE,
        GOOGLE_SHEET_ID,
        GOOGLE_SHEET_WORKSHEET
    )
    
    return {
        "configured": GOOGLE_SERVICE_ACCOUNT_FILE is not None and GOOGLE_SHEET_ID is not None,
        "service_account_file": str(GOOGLE_SERVICE_ACCOUNT_FILE) if GOOGLE_SERVICE_ACCOUNT_FILE else None,
        "sheet_id": GOOGLE_SHEET_ID,
        "worksheet": GOOGLE_SHEET_WORKSHEET,
    }