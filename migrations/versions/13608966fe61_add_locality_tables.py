"""Add locality tables

Revision ID: 13608966fe61
Revises: 00c0ff6fd3f2
Create Date: 2021-08-09 13:47:35.204306

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13608966fe61'
down_revision = '00c0ff6fd3f2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('country',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('area_two',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('country_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('area_one',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('area_two_id', sa.Integer(), nullable=True),
    sa.Column('country_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['area_two_id'], ['area_two.id'], ),
    sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('locality',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('area_one_id', sa.Integer(), nullable=True),
    sa.Column('area_two_id', sa.Integer(), nullable=True),
    sa.Column('country_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['area_one_id'], ['area_one.id'], ),
    sa.ForeignKeyConstraint(['area_two_id'], ['area_two.id'], ),
    sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('spot', sa.Column('locality_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_spot_locality', 'spot', 'locality', ['locality_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('fk_spot_locality', 'spot', type_='foreignkey')
    op.drop_column('spot', 'locality_id')
    op.drop_table('locality')
    op.drop_table('area_one')
    op.drop_table('area_two')
    op.drop_table('country')
    # ### end Alembic commands ###
