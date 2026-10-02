"""Add document soft deletion.

Revision ID: 178db1cb8a7c
Revises: d0329419bb46
Create Date: 2026-10-02 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "178db1cb8a7c"
down_revision: Union[str, Sequence[str], None] = "d0329419bb46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("documents", "deleted_at")
