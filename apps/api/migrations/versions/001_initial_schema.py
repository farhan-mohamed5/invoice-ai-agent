"""Initial schema for users and companies tables"""

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("clerk_id", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id")),
    )


def downgrade():
    op.drop_table("users")
    op.drop_table("companies")