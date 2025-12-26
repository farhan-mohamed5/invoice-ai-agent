<%text>
"""Alembic migration script."""
</%text>

revision = '${up_revision}'
down_revision = ${down_revision | repr}
branch_labels = ${branch_labels | repr}
depends_on = ${depends_on | repr}

from alembic import op
import sqlalchemy as sa


def upgrade():
    pass


def downgrade():
    pass