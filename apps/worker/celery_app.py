from celery import Celery

app = Celery(
    "invoice_agent_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

app.conf.update(
    task_routes={
        "process_receipt_task": {"queue": "invoices"},
        "sync_sheets_to_db_task": {"queue": "invoices"},
    },
    task_default_queue="invoices",
    
    # PERIODIC TASKS SCHEDULE
    beat_schedule={
        # Sync from Google Sheets every 5 minutes
        "sync-sheets-to-db": {
            "task": "sync_sheets_to_db_task",
            "schedule": 300.0,  # Every 5 minutes
        },
    },
    timezone="Asia/Dubai",
)

# Auto-discover tasks from tasks folder
app.autodiscover_tasks(["apps.worker.tasks"])