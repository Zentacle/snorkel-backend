"""Add description field for locations

Revision ID: 075b85d528dc
Revises: 02406a792cf4
Create Date: 2021-09-14 08:49:52.070476

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '075b85d528dc'
down_revision = '02406a792cf4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('area_one', sa.Column('description', sa.String(), nullable=True))
    op.add_column('area_two', sa.Column('description', sa.String(), nullable=True))
    op.add_column('country', sa.Column('description', sa.String(), nullable=True))
    op.add_column('locality', sa.Column('description', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('locality', 'description')
    op.drop_column('country', 'description')
    op.drop_column('area_two', 'description')
    op.drop_column('area_one', 'description')
    # ### end Alembic commands ###
