"""
Configuration for invoice processing pipeline.
All paths should be relative to PROJECT ROOT.
"""

import os
from enum import Enum
from pathlib import Path

# ============================================================
# Base Directories
# ============================================================


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
BASE_DIR = PROJECT_ROOT  # Alias for compatibility

# Data directory at project root
INVOICE_AGENT_DATA_DIR = PROJECT_ROOT / "invoice_agent_data"
DATA_ROOT = INVOICE_AGENT_DATA_DIR  # Alias for compatibility

# ============================================================
# Folder Paths
# ============================================================

# Inbox for uploaded files
INBOX_DIR = INVOICE_AGENT_DATA_DIR / "Invoices_Inbox"

# Organized invoices folder
INVOICES_DIR = INVOICE_AGENT_DATA_DIR / "Invoices"
OUTPUT_ROOT = INVOICES_DIR  # Alias for compatibility

# Database path
DB_PATH = INVOICE_AGENT_DATA_DIR / "invoices.db"

# Logs directory
LOG_DIR = INVOICE_AGENT_DATA_DIR / "logs"

# Create directories if they don't exist
for p in (INVOICE_AGENT_DATA_DIR, INBOX_DIR, INVOICES_DIR, LOG_DIR):
    p.mkdir(parents=True, exist_ok=True)

# ============================================================
# File Processing
# ============================================================

# Allowed file extensions
ALLOWED_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}

# ============================================================
# Google Sheets Configuration
# ============================================================

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
if GOOGLE_SERVICE_ACCOUNT_FILE:
    GOOGLE_SERVICE_ACCOUNT_FILE = Path(GOOGLE_SERVICE_ACCOUNT_FILE)

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_WORKSHEET = os.getenv("GOOGLE_SHEET_WORKSHEET", "Invoices")

# ============================================================
# OCR Configuration
# ============================================================

# OCR adapter: "tesseract" or "textract" (AWS)
OCR_ADAPTER = os.getenv("OCR_ADAPTER", "tesseract")

# AWS Textract (if using)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# ============================================================
# LLM Configuration
# ============================================================

# LLM provider: "ollama" or "openai"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# Ollama settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")



# ============================================================
# Invoice Status Enum
# ============================================================

class InvoiceStatus(str, Enum):
    """Invoice processing status."""
    OK = "ok"
    NEEDS_REVIEW = "needs_review"
    ERROR = "error"
    PENDING = "pending"
    PROCESSING = "processing"

# ============================================================
# UAE Business Defaults
# ============================================================

DEFAULT_CURRENCY = "AED"
DEFAULT_VAT_RATE = 0.05  # 5% VAT in UAE

# Default categories for UAE businesses
DEFAULT_CATEGORIES = [
    "Office Supplies",
    "Utilities",
    "Telecommunications",
    "Transportation",
    "Meals & Entertainment",
    "Professional Services",
    "Marketing",
    "Software & Subscriptions",
    "Rent",
    "Maintenance",
    "Insurance",
    "Other"
]

# ============================================================
# Confidence Thresholds
# ============================================================

# Minimum confidence to mark as "ok" vs "needs_review"
MIN_CONFIDENCE_OK = 0.7

# ============================================================
# Debug
# ============================================================

if __name__ == "__main__":
    print("📁 Invoice Agent Configuration")
    print("=" * 60)
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Data Directory: {INVOICE_AGENT_DATA_DIR}")
    print(f"Inbox: {INBOX_DIR}")
    print(f"Invoices: {INVOICES_DIR}")
    print(f"Database: {DB_PATH}")
    print(f"OCR Adapter: {OCR_ADAPTER}")
    print(f"LLM Provider: {LLM_PROVIDER}")
    print("=" * 60)
