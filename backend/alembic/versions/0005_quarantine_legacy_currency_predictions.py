"""Quarantine legacy checksum-derived currency predictions."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE counterfeit_cases
        SET prediction = 'Legacy Unverified',
            confidence = 0,
            explanation = '["Created by the retired checksum detector; rescan the note for a forensic verdict"]'
        WHERE prediction IN ('Real', 'Fake')
        """
    )


def downgrade() -> None:
    # The retired arbitrary verdict cannot be reconstructed safely.
    pass
