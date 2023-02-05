"""Add username for dive shops

Revision ID: 6428dfa7a6dc
Revises: f0de092d5fcf
Create Date: 2023-01-28 20:28:33.209703

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6428dfa7a6dc'
down_revision = 'f0de092d5fcf'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dive_shop', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username', sa.String(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dive_shop', schema=None) as batch_op:
        batch_op.drop_column('username')

    # ### end Alembic commands ###