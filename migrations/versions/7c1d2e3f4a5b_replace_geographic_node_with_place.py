"""Replace geographic_node with place

Drops the unused geographic_node hierarchy (no spot or shop pointed at it in
production; any rows are derived from the legacy location tables and can be
rebuilt) and adds the place table. See LOCATION_MIGRATION.md.

Revision ID: 7c1d2e3f4a5b
Revises: c41ee6a08991
Create Date: 2026-10-15 20:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7c1d2e3f4a5b"
down_revision = "c41ee6a08991"
branch_labels = None
depends_on = None


def upgrade():
    # --- remove geographic_node (IF EXISTS: tolerate partial state)
    op.execute("DROP INDEX IF EXISTS ix_spot_geographic_node_id")
    op.execute("DROP INDEX IF EXISTS ix_spot_geographic_verified_deleted")
    op.execute("DROP INDEX IF EXISTS ix_dive_shop_geographic_node_id")
    op.execute("ALTER TABLE spot DROP COLUMN IF EXISTS geographic_node_id")
    op.execute("ALTER TABLE dive_shop DROP COLUMN IF EXISTS geographic_node_id")
    op.execute("DROP TABLE IF EXISTS geographic_node CASCADE")

    # --- add place
    op.create_table(
        "place",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("lineage", sa.String(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("google_name", sa.String(), nullable=True),
        sa.Column("google_place_id", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("map_image_url", sa.String(), nullable=True),
        sa.Column("legacy_type", sa.String(), nullable=True),
        sa.Column("legacy_id", sa.Integer(), nullable=True),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["parent_id"], ["place.id"], name="fk_place_parent"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path", name="uq_place_path"),
        sa.UniqueConstraint("parent_id", "slug", name="uq_place_parent_slug"),
        sa.UniqueConstraint("legacy_type", "legacy_id", name="uq_place_legacy"),
    )
    op.create_index("ix_place_parent_id", "place", ["parent_id"])
    # text_pattern_ops so "lineage LIKE '/1/5/%'" uses the index
    op.execute("CREATE INDEX ix_place_lineage ON place (lineage text_pattern_ops)")

    op.add_column("spot", sa.Column("place_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_spot_place", "spot", "place", ["place_id"], ["id"])
    op.create_index("ix_spot_place_id", "spot", ["place_id"])

    op.add_column("dive_shop", sa.Column("place_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_dive_shop_place", "dive_shop", "place", ["place_id"], ["id"])
    op.create_index("ix_dive_shop_place_id", "dive_shop", ["place_id"])


def downgrade():
    op.drop_index("ix_dive_shop_place_id", table_name="dive_shop")
    op.drop_constraint("fk_dive_shop_place", "dive_shop", type_="foreignkey")
    op.drop_column("dive_shop", "place_id")
    op.drop_index("ix_spot_place_id", table_name="spot")
    op.drop_constraint("fk_spot_place", "spot", type_="foreignkey")
    op.drop_column("spot", "place_id")
    op.drop_table("place")

    # recreate the empty geographic_node schema (b4048382b892 + 5274015c42ef)
    op.create_table(
        "geographic_node",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("short_name", sa.String(), nullable=False),
        sa.Column("google_name", sa.String()),
        sa.Column("google_place_id", sa.String()),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("root_id", sa.Integer()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("country_code", sa.String(2)),
        sa.Column("admin_level", sa.Integer(), nullable=False),
        sa.Column("description", sa.String()),
        sa.Column("map_image_url", sa.String()),
        sa.Column("legacy_country_id", sa.Integer(), nullable=True),
        sa.Column("legacy_area_one_id", sa.Integer(), nullable=True),
        sa.Column("legacy_area_two_id", sa.Integer(), nullable=True),
        sa.Column("legacy_locality_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["geographic_node.id"], name="fk_geographic_node_parent"),
        sa.ForeignKeyConstraint(["root_id"], ["geographic_node.id"], name="fk_geographic_node_root"),
        sa.ForeignKeyConstraint(["legacy_country_id"], ["country.id"], name="fk_geographic_node_legacy_country"),
        sa.ForeignKeyConstraint(["legacy_area_one_id"], ["area_one.id"], name="fk_geographic_node_legacy_area_one"),
        sa.ForeignKeyConstraint(["legacy_area_two_id"], ["area_two.id"], name="fk_geographic_node_legacy_area_two"),
        sa.ForeignKeyConstraint(["legacy_locality_id"], ["locality.id"], name="fk_geographic_node_legacy_locality"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_unique_constraint("uq_geographic_node_parent_short_name", "geographic_node", ["parent_id", "short_name"])
    op.create_index("ix_geographic_node_parent_id", "geographic_node", ["parent_id"])
    op.create_index("ix_geographic_node_admin_level", "geographic_node", ["admin_level"])
    op.create_index("ix_geographic_node_short_name_admin_level", "geographic_node", ["short_name", "admin_level"])
    op.add_column("spot", sa.Column("geographic_node_id", sa.Integer(), nullable=True))
    op.create_foreign_key("spot_geographic_node_id_fkey", "spot", "geographic_node", ["geographic_node_id"], ["id"])
    op.create_index("ix_spot_geographic_node_id", "spot", ["geographic_node_id"])
    op.create_index("ix_spot_geographic_verified_deleted", "spot", ["geographic_node_id", "is_verified", "is_deleted"])
    op.add_column("dive_shop", sa.Column("geographic_node_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "dive_shop_geographic_node_id_fkey", "dive_shop", "geographic_node", ["geographic_node_id"], ["id"]
    )
    op.create_index("ix_dive_shop_geographic_node_id", "dive_shop", ["geographic_node_id"])
