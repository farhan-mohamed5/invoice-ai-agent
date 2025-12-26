"""SQLite-safe migration to update receipts table schema"""

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from datetime import datetime


def upgrade():
    # 1. Rename current receipts → receipts_old
    op.rename_table("receipts", "receipts_old")

    # 2. Create new receipts table (correct final schema)
    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),

        sa.Column("file_original_name", sa.String(), nullable=False),
        sa.Column("file_new_path", sa.String(), nullable=True),
        sa.Column("date", sa.String(), nullable=True),
        sa.Column("vendor", sa.String(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("tax_amount", sa.Float(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("payment_method", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # 3. Copy data from old receipts table into new one
    conn = op.get_bind()
    
    rows = conn.execute(sa.text("SELECT * FROM receipts_old")).fetchall()

    now = datetime.utcnow()

    for row in rows:
        conn.execute(
            sa.text("""
                INSERT INTO receipts (
                    id, company_id, file_original_name, file_new_path, date, vendor,
                    amount, currency, tax_amount, category, payment_method, source,
                    ocr_confidence, extraction_confidence, status, notes,
                    created_at, updated_at
                )
                VALUES (
                    :id, NULL, :file_original_name, :file_new_path, :date, :vendor,
                    :amount, :currency, :tax_amount, :category, :payment_method, :source,
                    :ocr_confidence, :extraction_confidence, :status, :notes,
                    :created_at, :updated_at
                )
            """),
            {
                "id": row["id"],
                "file_original_name": row["file_original_name"],
                "file_new_path": row["file_new_path"],
                "date": row["date"],
                "vendor": row["vendor"],
                "amount": row["amount"],
                "currency": row["currency"],
                "tax_amount": row["tax_amount"],
                "category": row["category"],
                "payment_method": row["payment_method"],
                "source": row["source"],
                "ocr_confidence": row["ocr_confidence"],
                "extraction_confidence": row["extraction_confidence"],
                "status": row["status"],
                "notes": row["notes"],
                "created_at": now,
                "updated_at": now,
            }
        )

    # 4. Drop old table
    op.drop_table("receipts_old")


def downgrade():
    raise NotImplementedError("Downgrade not supported for SQLite safe migration.")