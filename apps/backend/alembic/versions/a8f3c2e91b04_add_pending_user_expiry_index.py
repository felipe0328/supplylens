"""Add pending user expiry index

Revision ID: a8f3c2e91b04
Revises: 143d642d0e46
Create Date: 2026-10-15 21:15:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8f3c2e91b04"
down_revision: Union[str, Sequence[str], None] = "143d642d0e46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_users_pending_expires_at",
        "users",
        ["pending_expires_at"],
        unique=False,
        postgresql_where="status = 'PENDING'",
    )


def downgrade() -> None:
    op.drop_index("ix_users_pending_expires_at", table_name="users")
