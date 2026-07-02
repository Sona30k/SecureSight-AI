"""Add forensic currency detection fields."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("counterfeit_cases")}
    additions = {
        "corrected_image_path": sa.Column("corrected_image_path", sa.String(500), nullable=True),
        "heatmap_path": sa.Column("heatmap_path", sa.String(500), nullable=True),
        "authenticity_score": sa.Column("authenticity_score", sa.Integer(), nullable=False, server_default="0"),
        "counterfeit_probability": sa.Column("counterfeit_probability", sa.Float(), nullable=False, server_default="0"),
        "denomination": sa.Column("denomination", sa.String(10), nullable=True),
        "serial_number": sa.Column("serial_number", sa.String(30), nullable=True),
        "serial_duplicate": sa.Column("serial_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()),
        "location": sa.Column("location", sa.String(150), nullable=True),
        "bounding_box": sa.Column("bounding_box", sa.JSON(), nullable=False, server_default="{}"),
        "detected_features": sa.Column("detected_features", sa.JSON(), nullable=False, server_default="{}"),
        "explanation": sa.Column("explanation", sa.JSON(), nullable=False, server_default="[]"),
    }
    with op.batch_alter_table("counterfeit_cases") as batch:
        for name, column in additions.items():
            if name not in columns:
                batch.add_column(column)
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("counterfeit_cases")}
    with op.batch_alter_table("counterfeit_cases") as batch:
        for name in ("authenticity_score", "denomination", "serial_number", "serial_duplicate", "location"):
            index_name = f"ix_counterfeit_cases_{name}"
            if index_name not in indexes:
                batch.create_index(index_name, [name])


def downgrade() -> None:
    with op.batch_alter_table("counterfeit_cases") as batch:
        for name in (
            "explanation", "detected_features", "bounding_box", "location", "serial_duplicate",
            "serial_number", "denomination", "counterfeit_probability", "authenticity_score",
            "heatmap_path", "corrected_image_path",
        ):
            batch.drop_column(name)
