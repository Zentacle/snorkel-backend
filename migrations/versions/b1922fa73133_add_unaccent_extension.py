"""add unaccent extension

Revision ID: b1922fa73133
Revises: f85c26c91798
Create Date: 2025-07-06 11:38:29.133126

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b1922fa73133"
down_revision = "f85c26c91798"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")


def downgrade():
    op.execute("DROP EXTENSION IF EXISTS unaccent;")
