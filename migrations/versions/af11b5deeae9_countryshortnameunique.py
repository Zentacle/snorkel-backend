"""CountryShortNameUnique

Revision ID: af11b5deeae9
Revises: f4419a389f13
Create Date: 2022-05-15 21:41:41.801543

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af11b5deeae9'
down_revision = 'f4419a389f13'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint('country_short_name_key', 'country', ['short_name'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('country_short_name_key', 'country', type_='unique')
    # ### end Alembic commands ###
