"""Update image URLs

Revision ID: 9def8bd5d54f
Revises: dbbd634bd9cf
Create Date: 2022-09-24 16:17:07.575687

"""
from alembic import op
import sqlalchemy as sa
from app.models import Image

# revision identifiers, used by Alembic.
revision = '9def8bd5d54f'
down_revision = 'dbbd634bd9cf'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)

    for image in session.query(Image).all():
        if not 'https://' in image.url:
            image.url = f'https://www.zentacle.com/image/reviews/{image.url}'
        elif 'https://snorkel.s3.amazonaws.com/' in image.url:
            image.url = image.url.replace('https://snorkel.s3.amazonaws.com/', 'https://www.zentacle.com/image/')
        else:
            image.url = image.url

    session.commit()
    pass


def downgrade():
    pass
