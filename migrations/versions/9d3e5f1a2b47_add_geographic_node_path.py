"""Add stored public URL path to geographic_node

Revision ID: 9d3e5f1a2b47
Revises: c41ee6a08991
Create Date: 2026-10-15 18:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9d3e5f1a2b47"
down_revision = "c41ee6a08991"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("geographic_node", sa.Column("path", sa.String(), nullable=True))
    op.create_unique_constraint("uq_geographic_node_path", "geographic_node", ["path"])


def downgrade():
    op.drop_constraint("uq_geographic_node_path", "geographic_node", type_="unique")
    op.drop_column("geographic_node", "path")
