"""add_geo_node_indexes

Revision ID: 5274015c42ef
Revises: b4048382b892
Create Date: 2025-07-06 14:20:13.494910

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5274015c42ef"
down_revision = "b4048382b892"
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for geographic queries"""

    # Index for geographic node hierarchy queries
    op.create_index("ix_geographic_node_parent_id", "geographic_node", ["parent_id"])

    # Index for geographic node admin level queries
    op.create_index(
        "ix_geographic_node_admin_level", "geographic_node", ["admin_level"]
    )

    # Composite index for path lookups
    op.create_index(
        "ix_geographic_node_short_name_admin_level",
        "geographic_node",
        ["short_name", "admin_level"],
    )

    # Index for spot geographic queries
    op.create_index("ix_spot_geographic_node_id", "spot", ["geographic_node_id"])

    # Composite index for spot filtering and sorting
    op.create_index(
        "ix_spot_geographic_verified_deleted",
        "spot",
        ["geographic_node_id", "is_verified", "is_deleted"],
    )

    # Index for spot sorting by reviews
    op.create_index("ix_spot_num_reviews", "spot", ["num_reviews"])

    # Index for spot sorting by rating
    op.create_index("ix_spot_rating", "spot", ["rating"])

    # Index for spot sorting by last review date
    op.create_index("ix_spot_last_review_date", "spot", ["last_review_date"])

    # Index for dive shop geographic queries
    op.create_index(
        "ix_dive_shop_geographic_node_id", "dive_shop", ["geographic_node_id"]
    )

    # Index for dive shop sorting by rating
    op.create_index("ix_dive_shop_rating", "dive_shop", ["rating"])

    # Index for dive shop sorting by reviews
    op.create_index("ix_dive_shop_num_reviews", "dive_shop", ["num_reviews"])

    # Index for dive shop sorting by created date
    op.create_index("ix_dive_shop_created", "dive_shop", ["created"])


def downgrade():
    """Remove performance indexes"""

    op.drop_index("ix_geographic_node_parent_id", table_name="geographic_node")
    op.drop_index("ix_geographic_node_admin_level", table_name="geographic_node")
    op.drop_index(
        "ix_geographic_node_short_name_admin_level", table_name="geographic_node"
    )
    op.drop_index("ix_spot_geographic_node_id", table_name="spot")
    op.drop_index("ix_spot_geographic_verified_deleted", table_name="spot")
    op.drop_index("ix_spot_num_reviews", table_name="spot")
    op.drop_index("ix_spot_rating", table_name="spot")
    op.drop_index("ix_spot_last_review_date", table_name="spot")
    op.drop_index("ix_dive_shop_geographic_node_id", table_name="dive_shop")
    op.drop_index("ix_dive_shop_rating", table_name="dive_shop")
    op.drop_index("ix_dive_shop_num_reviews", table_name="dive_shop")
    op.drop_index("ix_dive_shop_created", table_name="dive_shop")
