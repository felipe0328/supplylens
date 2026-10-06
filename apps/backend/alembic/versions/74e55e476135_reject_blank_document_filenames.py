"""Reject blank document filenames.

Revision ID: 74e55e476135
Revises: 178db1cb8a7c
Create Date: 2026-10-02 00:01:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "74e55e476135"
down_revision: Union[str, Sequence[str], None] = "178db1cb8a7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE documents
            SET filename = 'document-' || id::text || '.pdf'
            WHERE trim(filename) = ''
            """
        )
    )
    op.drop_constraint("ck_document_filename_not_empty", "documents", type_="check")
    op.create_check_constraint(
        "ck_document_filename_not_empty", "documents", "trim(filename) <> ''"
    )


def downgrade() -> None:
    op.drop_constraint("ck_document_filename_not_empty", "documents", type_="check")
    op.create_check_constraint(
        "ck_document_filename_not_empty", "documents", "filename <> ''"
    )
