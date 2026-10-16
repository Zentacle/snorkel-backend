"""Add spot.merged_into_id so merged (deleted) spots can redirect

Revision ID: 3e8a9b0c1d2f
Revises: 7c1d2e3f4a5b
Create Date: 2026-10-16 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3e8a9b0c1d2f"
down_revision = "7c1d2e3f4a5b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("spot", sa.Column("merged_into_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_spot_merged_into", "spot", "spot", ["merged_into_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_spot_merged_into", "spot", type_="foreignkey")
    op.drop_column("spot", "merged_into_id")
