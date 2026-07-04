"""Add live call, external dispatch, currency device and validation records."""

import sqlalchemy as sa
from alembic import op

from app.database.base import Base

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in (
        "currency_devices", "currency_reviews", "live_call_sessions",
        "integration_dispatches",
    ):
        if name not in existing:
            Base.metadata.tables[name].create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    for name in (
        "integration_dispatches", "live_call_sessions",
        "currency_reviews", "currency_devices",
    ):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
