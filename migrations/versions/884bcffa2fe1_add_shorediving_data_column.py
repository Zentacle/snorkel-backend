"""Add shorediving data column

Revision ID: 884bcffa2fe1
Revises: be6780890e25
Create Date: 2021-09-08 12:15:45.281267

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '884bcffa2fe1'
down_revision = 'be6780890e25'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('shore_diving_data',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('name_url', sa.String(), nullable=True),
    sa.Column('destination', sa.String(), nullable=True),
    sa.Column('destination_url', sa.String(), nullable=True),
    sa.Column('region', sa.String(), nullable=True),
    sa.Column('region_url', sa.String(), nullable=True),
    sa.Column('spot_id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_foreign_key('fk_sd_data_spot', 'shore_diving_data', 'spot', ['spot_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('fk_sd_data_spot', 'spot', type_='foreignkey')
    op.drop_table('shore_diving_data')
    # ### end Alembic commands ###
