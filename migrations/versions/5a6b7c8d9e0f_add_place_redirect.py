"""Add place_redirect: old location URLs that 301 to a place

Revision ID: 5a6b7c8d9e0f
Revises: 3e8a9b0c1d2f
Create Date: 2026-10-16 18:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5a6b7c8d9e0f"
down_revision = "3e8a9b0c1d2f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "place_redirect",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("place_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["place_id"], ["place.id"], name="fk_place_redirect_place"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path", name="uq_place_redirect_path"),
    )
    op.create_index("ix_place_redirect_place_id", "place_redirect", ["place_id"])


def downgrade():
    op.drop_index("ix_place_redirect_place_id", table_name="place_redirect")
    op.drop_table("place_redirect")
