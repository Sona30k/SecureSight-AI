"""Track currency series and legal-tender status."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("counterfeit_cases")}
    indexes = {index["name"] for index in inspector.get_indexes("counterfeit_cases")}
    with op.batch_alter_table("counterfeit_cases") as batch:
        if "series" not in columns:
            batch.add_column(sa.Column("series", sa.String(80), nullable=True))
        if "legal_tender" not in columns:
            batch.add_column(sa.Column("legal_tender", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "currency_status" not in columns:
            batch.add_column(sa.Column("currency_status", sa.String(160), nullable=True))
        if "ix_counterfeit_cases_series" not in indexes:
            batch.create_index("ix_counterfeit_cases_series", ["series"])
        if "ix_counterfeit_cases_legal_tender" not in indexes:
            batch.create_index("ix_counterfeit_cases_legal_tender", ["legal_tender"])


def downgrade() -> None:
    with op.batch_alter_table("counterfeit_cases") as batch:
        batch.drop_index("ix_counterfeit_cases_legal_tender")
        batch.drop_index("ix_counterfeit_cases_series")
        batch.drop_column("currency_status")
        batch.drop_column("legal_tender")
        batch.drop_column("series")
