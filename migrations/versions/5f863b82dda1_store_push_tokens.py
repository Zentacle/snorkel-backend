"""Store push tokens

Revision ID: 5f863b82dda1
Revises: 9def8bd5d54f
Create Date: 2023-01-10 21:47:21.487116

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5f863b82dda1'
down_revision = '9def8bd5d54f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('push_token', sa.String(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'push_token')

    # ### end Alembic commands ###
