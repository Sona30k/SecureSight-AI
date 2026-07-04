"""Add multi-agency graph ingestion and evidence custody records."""

import sqlalchemy as sa
from alembic import op

from app.database.base import Base

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in (
        "intelligence_feeds", "graph_ingestion_batches", "graph_events",
        "evidence_items", "evidence_custody_events", "case_exchanges",
    ):
        if name not in existing:
            Base.metadata.tables[name].create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    for name in (
        "case_exchanges", "evidence_custody_events", "evidence_items",
        "graph_events", "graph_ingestion_batches", "intelligence_feeds",
    ):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
