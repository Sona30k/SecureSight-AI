"""Add GIS, district-sharing, channel, and speech-stream records."""

import sqlalchemy as sa
from alembic import op

from app.database.base import Base

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in (
        "gis_feeds", "district_intelligence_shares", "speech_streams",
        "channel_interactions", "government_submissions",
    ):
        if name not in existing:
            Base.metadata.tables[name].create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    for name in (
        "government_submissions", "channel_interactions", "speech_streams",
        "district_intelligence_shares", "gis_feeds",
    ):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
