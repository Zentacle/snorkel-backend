"""AddUserUnits

Revision ID: f4419a389f13
Revises: d1d65dddc251
Create Date: 2022-05-11 15:07:11.430804

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4419a389f13'
down_revision = 'd1d65dddc251'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('unit', sa.String(), nullable=True))
    op.execute('UPDATE public.user SET unit = \'imperial\'')
    op.alter_column('user', 'unit', nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'unit')
    # ### end Alembic commands ###
