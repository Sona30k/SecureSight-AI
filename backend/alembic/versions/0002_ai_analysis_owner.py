"""Track the user who requested every AI analysis."""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("ai_analyses")}
    if "requested_by" not in columns:
        with op.batch_alter_table("ai_analyses") as batch:
            batch.add_column(sa.Column("requested_by", sa.Uuid(), nullable=True))
            batch.create_index("ix_ai_analyses_requested_by", ["requested_by"])
            batch.create_foreign_key("fk_ai_analyses_requested_by_users", "users", ["requested_by"], ["id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("ai_analyses")}
    if "requested_by" in columns:
        with op.batch_alter_table("ai_analyses") as batch:
            batch.drop_constraint("fk_ai_analyses_requested_by_users", type_="foreignkey")
            batch.drop_index("ix_ai_analyses_requested_by")
            batch.drop_column("requested_by")
