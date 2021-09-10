"""Add extra shorediving review table columns

Revision ID: 91db0f46f796
Revises: 4561393dfdd5
Create Date: 2021-09-10 13:41:16.366802

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91db0f46f796'
down_revision = '4561393dfdd5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('shore_diving_review', sa.Column('entry', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('bottom', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('reef', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('animal', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('plant', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('facilities', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('crowds', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('roads', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('snorkel', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('beginner', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('intermediate', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('advanced', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('night', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('visibility', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('current', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('surf', sa.Integer(), nullable=True))
    op.add_column('shore_diving_review', sa.Column('average', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('shore_diving_review', 'average')
    op.drop_column('shore_diving_review', 'surf')
    op.drop_column('shore_diving_review', 'current')
    op.drop_column('shore_diving_review', 'visibility')
    op.drop_column('shore_diving_review', 'night')
    op.drop_column('shore_diving_review', 'advanced')
    op.drop_column('shore_diving_review', 'intermediate')
    op.drop_column('shore_diving_review', 'beginner')
    op.drop_column('shore_diving_review', 'snorkel')
    op.drop_column('shore_diving_review', 'roads')
    op.drop_column('shore_diving_review', 'crowds')
    op.drop_column('shore_diving_review', 'facilities')
    op.drop_column('shore_diving_review', 'plant')
    op.drop_column('shore_diving_review', 'animal')
    op.drop_column('shore_diving_review', 'reef')
    op.drop_column('shore_diving_review', 'bottom')
    op.drop_column('shore_diving_review', 'entry')
    # ### end Alembic commands ###
