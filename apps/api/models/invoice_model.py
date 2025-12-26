from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from apps.api.core.db import Base


class Invoice(Base):
    __tablename__ = "invoices"

    # Matches existing SQLite PRIMARY KEY AUTOINCREMENT
    id = Column(Integer, primary_key=True, autoincrement=True)

    import_timestamp = Column(String, nullable=True)

    # New multi-tenant column (nullable for existing data)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)

    # --- REQUIRED fields  ---
    file_original_name = Column(String, nullable=False)
    file_new_path = Column(String, nullable=True)   # existing SQLite uses this name, not file_path
    source = Column(String, nullable=False)         # pdf_text / ocr_image / local

    # --- OPTIONAL extracted fields ---
    date = Column(String, nullable=True)            # stored as TEXT in SQLite
    vendor = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    tax_amount = Column(Float, nullable=True)
    category = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)

    # --- New classification fields ---
    transaction_type = Column(String, nullable=True)   # "b2b" or "operational_expense"
    is_paid = Column(Integer, nullable=True)            # 1 / 0 / NULL

    # --- Confidence fields ---
    ocr_confidence = Column(Float, nullable=True)
    extraction_confidence = Column(Float, nullable=True)

    # --- Status + Notes ---
    status = Column(String, nullable=False)         # "ok", "needs_review", etc.
    notes = Column(String, nullable=True)

    # --- Review workflow  ---
    # JSON-serialized list of questions when status = "needs_review"
    review_questions = Column(Text, nullable=True)
    # Human-readable reason why review is needed
    review_reason = Column(String, nullable=True)

    # --- Timestamps ---
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationship back to the company
    company = relationship("Company", back_populates="invoices")