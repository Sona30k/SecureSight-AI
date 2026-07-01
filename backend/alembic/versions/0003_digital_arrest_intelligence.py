"""Add the complete digital arrest intelligence domain."""

import sqlalchemy as sa
from alembic import op

from app.database.base import Base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for table_name in ("call_transcripts", "risk_analyses", "digital_arrest_evidence", "caller_histories"):
        if table_name not in existing_tables:
            Base.metadata.tables[table_name].create(bind=bind)

    columns = {column["name"] for column in sa.inspect(bind).get_columns("digital_arrest_cases")}
    additions = {
        "country": sa.Column("country", sa.String(100), nullable=True),
        "confidence": sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        "threat_level": sa.Column("threat_level", sa.String(20), nullable=False, server_default="low"),
        "explanation": sa.Column("explanation", sa.JSON(), nullable=False, server_default="[]"),
        "manipulation_techniques": sa.Column("manipulation_techniques", sa.JSON(), nullable=False, server_default="[]"),
        "psychological_signals": sa.Column("psychological_signals", sa.JSON(), nullable=False, server_default="{}"),
        "conversation_stages": sa.Column("conversation_stages", sa.JSON(), nullable=False, server_default="[]"),
        "status": sa.Column("status", sa.String(30), nullable=False, server_default="analyzed"),
        "blocked": sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        "police_notified": sa.Column("police_notified", sa.Boolean(), nullable=False, server_default=sa.false()),
        "report_saved": sa.Column("report_saved", sa.Boolean(), nullable=False, server_default=sa.false()),
    }
    with op.batch_alter_table("digital_arrest_cases") as batch:
        for name, column in additions.items():
            if name not in columns:
                batch.add_column(column)

    refreshed = {column["name"] for column in sa.inspect(bind).get_columns("digital_arrest_cases")}
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("digital_arrest_cases")}
    with op.batch_alter_table("digital_arrest_cases") as batch:
        for name in ("threat_level", "status", "blocked", "police_notified", "report_saved"):
            index_name = f"ix_digital_arrest_cases_{name}"
            if name in refreshed and index_name not in indexes:
                batch.create_index(index_name, [name])


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in ("caller_histories", "digital_arrest_evidence", "risk_analyses", "call_transcripts"):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
    with op.batch_alter_table("digital_arrest_cases") as batch:
        for name in (
            "report_saved", "police_notified", "blocked", "status", "conversation_stages",
            "psychological_signals", "manipulation_techniques", "explanation", "threat_level",
            "confidence", "country",
        ):
            batch.drop_column(name)
