"""Add explicit outcome status to enterprise audit records."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("audit_logs")}
    if "status" not in columns:
        with op.batch_alter_table("audit_logs") as batch:
            batch.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="success"))
            batch.create_index("ix_audit_logs_status", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("audit_logs")}
    if "status" in columns:
        with op.batch_alter_table("audit_logs") as batch:
            batch.drop_index("ix_audit_logs_status")
            batch.drop_column("status")
