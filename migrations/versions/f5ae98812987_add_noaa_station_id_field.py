"""Add noaa station id field

Revision ID: f5ae98812987
Revises: 7c7a70eb62f8
Create Date: 2021-10-17 19:16:56.267485

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5ae98812987'
down_revision = '7c7a70eb62f8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('spot', sa.Column('noaa_station_id', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('spot', 'noaa_station_id')
    # ### end Alembic commands ###
