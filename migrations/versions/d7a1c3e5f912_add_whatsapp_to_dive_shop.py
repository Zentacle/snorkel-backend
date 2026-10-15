"""Add WhatsApp to dive shop

Revision ID: d7a1c3e5f912
Revises: c41ee6a08991
Create Date: 2026-10-14 22:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d7a1c3e5f912"
down_revision = "c41ee6a08991"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("dive_shop", schema=None) as batch_op:
        batch_op.add_column(sa.Column("whatsapp", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("dive_shop", schema=None) as batch_op:
        batch_op.drop_column("whatsapp")
