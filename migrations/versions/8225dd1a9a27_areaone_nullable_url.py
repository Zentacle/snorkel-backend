"""AreaOne nullable url

Revision ID: 8225dd1a9a27
Revises: 2c66e1a24dd0
Create Date: 2022-08-04 13:05:47.463337

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8225dd1a9a27'
down_revision = '2c66e1a24dd0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('area_one', 'url',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('area_one', 'url',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###
