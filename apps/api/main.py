from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.db import run_migrations

# Routers
from apps.api.routes import invoices, system, auth, companies, upload
from apps.api.routes.files import router as files_router
from apps.api.routes.sheets import router as sheets_router

app = FastAPI(
    title="Invoice Agent API",
    version="1.0.0",
)

# ==========================
# CORS (Required for Next.js)
# ==========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# Startup Event
# ==========================
@app.on_event("startup")
def startup_event():
    run_migrations()
    print("✓ Database initialized")
    print("✓ Invoice Agent API is running")

# ==========================
# Routers
# ==========================
app.include_router(system.router, prefix="/system", tags=["system"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
app.include_router(files_router, prefix="/files", tags=["files"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(sheets_router)

# ==========================
# Root Endpoint
# ==========================
@app.get("/")
def root():
    return {
        "service": "invoice-agent-api",
        "status": "running",
        "endpoints": {
            "system": "/system/health",
            "invoices": "/invoices/",
            "companies": "/companies/",
            "auth": "/auth/me",
            "files": "/files/{invoice_id}",
            "upload": "/upload/",
            "sheets": "/api/sheets/sync-status",
        },
    }
