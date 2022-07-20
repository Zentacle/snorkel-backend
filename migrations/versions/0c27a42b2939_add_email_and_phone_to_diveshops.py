"""Add email and phone to diveshops

Revision ID: 0c27a42b2939
Revises: da269d451515
Create Date: 2022-07-20 18:12:48.559050

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0c27a42b2939'
down_revision = 'da269d451515'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('dive_shop', sa.Column('email', sa.String(), nullable=True))
    op.add_column('dive_shop', sa.Column('phone', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('dive_shop', 'phone')
    op.drop_column('dive_shop', 'email')
    # ### end Alembic commands ###
