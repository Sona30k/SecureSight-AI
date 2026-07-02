"""Add verified accounts, sessions, refresh tokens, OTPs and normalized RBAC."""

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.database.base import Base
from app.models import AccountStatus

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

ROLE_PERMISSIONS = {
    "citizen": ("fraud.report", "assistant.use", "currency.scan", "reports.view_own"),
    "police": ("investigations.manage", "crime_map.view", "fraud_network.view", "evidence.view", "analytics.view"),
    "bank": ("currency.scan", "fraud_transactions.view", "risk_reports.view"),
    "telecom_provider": ("scam_numbers.manage", "spoof_detection.use", "call_analytics.view"),
    "administrator": ("platform.manage",),
}


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table_name in ("roles", "permissions", "user_sessions", "refresh_tokens", "otps", "role_permissions"):
        if table_name not in existing:
            Base.metadata.tables[table_name].create(bind=bind)

    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    additions = {
        "account_status": sa.Column("account_status", sa.Enum(AccountStatus), nullable=False, server_default="verified"),
        "phone": sa.Column("phone", sa.String(20), nullable=True),
        "email_verified": sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
        "phone_verified": sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
        "state": sa.Column("state", sa.String(100), nullable=True),
        "district": sa.Column("district", sa.String(100), nullable=True),
        "preferred_language": sa.Column("preferred_language", sa.String(30), nullable=False, server_default="English"),
        "organization": sa.Column("organization", sa.String(180), nullable=True),
        "employee_id": sa.Column("employee_id", sa.String(80), nullable=True),
        "badge_number": sa.Column("badge_number", sa.String(80), nullable=True),
        "police_station": sa.Column("police_station", sa.String(180), nullable=True),
        "department": sa.Column("department", sa.String(150), nullable=True),
        "rank": sa.Column("rank", sa.String(100), nullable=True),
        "branch": sa.Column("branch", sa.String(180), nullable=True),
        "profile_picture": sa.Column("profile_picture", sa.String(500), nullable=True),
        "notification_preferences": sa.Column("notification_preferences", sa.JSON(), nullable=False, server_default='{"email":true,"sms":true,"push":true}'),
        "failed_login_attempts": sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        "locked_until": sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        "last_login_at": sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        "approved_by": sa.Column("approved_by", sa.Uuid(), nullable=True),
        "approved_at": sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    }
    with op.batch_alter_table("users") as batch:
        for name, column in additions.items():
            if name not in columns:
                batch.add_column(column)
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    with op.batch_alter_table("users") as batch:
        for name, unique in (
            ("account_status", False), ("phone", True), ("employee_id", False), ("badge_number", False),
        ):
            index_name = f"ix_users_{name}"
            if index_name not in indexes:
                batch.create_index(index_name, [name], unique=unique)

    now = datetime.now(timezone.utc)
    role_table, permission_table = Base.metadata.tables["roles"], Base.metadata.tables["permissions"]
    role_permission_table = Base.metadata.tables["role_permissions"]
    existing_roles = set(bind.execute(sa.select(role_table.c.name)).scalars())
    for role, permissions in ROLE_PERMISSIONS.items():
        if role not in existing_roles:
            bind.execute(role_table.insert().values(
                id=uuid4(), name=role, description=f"ShieldIQ {role.replace('_', ' ')} role",
                created_at=now, updated_at=now,
            ))
        for permission in permissions:
            if not bind.execute(sa.select(permission_table.c.code).where(permission_table.c.code == permission)).scalar():
                bind.execute(permission_table.insert().values(
                    id=uuid4(), code=permission, description=permission.replace(".", " ").replace("_", " ").title(),
                    created_at=now, updated_at=now,
                ))
            if not bind.execute(sa.select(role_permission_table.c.id).where(
                role_permission_table.c.role_name == role,
                role_permission_table.c.permission_code == permission,
            )).scalar():
                bind.execute(role_permission_table.insert().values(
                    id=uuid4(), role_name=role, permission_code=permission,
                ))


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in ("role_permissions", "refresh_tokens", "otps", "user_sessions", "permissions", "roles"):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
    with op.batch_alter_table("users") as batch:
        for name in (
            "approved_at", "approved_by", "last_login_at", "locked_until", "failed_login_attempts",
            "notification_preferences", "profile_picture", "branch", "rank", "department",
            "police_station", "badge_number", "employee_id", "organization", "preferred_language",
            "district", "state", "phone_verified", "email_verified", "phone", "account_status",
        ):
            batch.drop_column(name)
