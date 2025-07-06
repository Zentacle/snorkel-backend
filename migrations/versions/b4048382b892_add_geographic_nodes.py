"""Add geographic nodes table and migrate existing data

Revision ID: b4048382b892
Revises: f85c26c91798
Create Date: 2025-07-05 14:13:56.938428

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b4048382b892'
down_revision = 'f85c26c91798'
branch_labels = None
depends_on = None

def upgrade():
    # Create geographic_nodes table
    op.create_table('geographic_node',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('short_name', sa.String(), nullable=False),
        sa.Column('google_name', sa.String()),
        sa.Column('google_place_id', sa.String()),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('root_id', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        sa.Column('country_code', sa.String(2)),
        sa.Column('admin_level', sa.Integer(), nullable=False),
        sa.Column('description', sa.String()),
        sa.Column('map_image_url', sa.String()),
        sa.Column('legacy_country_id', sa.Integer(), nullable=True),
        sa.Column('legacy_area_one_id', sa.Integer(), nullable=True),
        sa.Column('legacy_area_two_id', sa.Integer(), nullable=True),
        sa.Column('legacy_locality_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['geographic_node.id'], name='fk_geographic_node_parent'),
        sa.ForeignKeyConstraint(['root_id'], ['geographic_node.id'], name='fk_geographic_node_root'),
        sa.ForeignKeyConstraint(['legacy_country_id'], ['country.id'], name='fk_geographic_node_legacy_country'),
        sa.ForeignKeyConstraint(['legacy_area_one_id'], ['area_one.id'], name='fk_geographic_node_legacy_area_one'),
        sa.ForeignKeyConstraint(['legacy_area_two_id'], ['area_two.id'], name='fk_geographic_node_legacy_area_two'),
        sa.ForeignKeyConstraint(['legacy_locality_id'], ['locality.id'], name='fk_geographic_node_legacy_locality'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create unique constraint on (parent_id, short_name) instead of just short_name
    op.create_unique_constraint('uq_geographic_node_parent_short_name', 'geographic_node', ['parent_id', 'short_name'])

    # Add geographic_node_id to spots table
    op.add_column('spot', sa.Column('geographic_node_id', sa.Integer(), nullable=True))
    op.create_foreign_key('spot_geographic_node_id_fkey', 'spot', 'geographic_node', ['geographic_node_id'], ['id'])

    # Add geographic_node_id to dive_shop table
    op.add_column('dive_shop', sa.Column('geographic_node_id', sa.Integer(), nullable=True))
    op.create_foreign_key('dive_shop_geographic_node_id_fkey', 'dive_shop', 'geographic_node', ['geographic_node_id'], ['id'])

def downgrade():
    # Remove foreign key constraints with explicit names
    op.drop_constraint('dive_shop_geographic_node_id_fkey', 'dive_shop', type_='foreignkey')
    op.drop_constraint('spot_geographic_node_id_fkey', 'spot', type_='foreignkey')

    # Remove columns
    op.drop_column('dive_shop', 'geographic_node_id')
    op.drop_column('spot', 'geographic_node_id')

    # Drop geographic_nodes table (this will automatically drop all constraints)
    op.drop_table('geographic_node')
