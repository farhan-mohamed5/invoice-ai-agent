from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


# ============================================================
# Review question structure
# ============================================================
class ReviewQuestionOption(BaseModel):
    value: Any
    label: str


class ReviewQuestion(BaseModel):
    field_name: str
    question: str
    input_type: str  # "text", "number", "date", "select", "confirm_or_correct"
    current_value: Optional[Any] = None
    hint: Optional[str] = None
    options: Optional[List[ReviewQuestionOption]] = None


# ============================================================
# Base shared fields 
# ============================================================
class InvoiceBase(BaseModel):
    file_original_name: Optional[str] = None
    file_new_path: Optional[str] = None
    date: Optional[str] = None
    vendor: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    tax_amount: Optional[float] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None
    # New features
    transaction_type: Optional[str] = None  # "b2b" | "operational_expense"
    is_paid: Optional[bool] = None
    source: Optional[str] = None
    ocr_confidence: Optional[float] = None
    extraction_confidence: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    # Review workflow fields
    review_reason: Optional[str] = None
    review_questions: Optional[List[ReviewQuestion]] = None


# ============================================================
# Create Schema
# ============================================================
class InvoiceCreate(InvoiceBase):
    file_original_name: str
    source: str
    status: str


# ============================================================
# Update Schema 
# ============================================================
class InvoiceUpdate(BaseModel):
    transaction_type: Optional[str] = None
    is_paid: Optional[bool] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None


# ============================================================
# Resolve Review Request 
# ============================================================
class ResolveReviewRequest(BaseModel):
    """
    User's answers to the review questions.
    Keys are field names, values are the answers.
    Example:
    {
        "amount": 1500.00,
        "is_paid": true,
        "category": "Occupancy & Facilities"
    }
    """
    answers: dict[str, Any]


class ResolveReviewResponse(BaseModel):
    success: bool
    message: str
    invoice: Optional["InvoiceOut"] = None


# ============================================================
# OUT Schema 
# ============================================================
class InvoiceOut(InvoiceBase):
    id: int
    company_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Fix forward reference
ResolveReviewResponse.model_rebuild()