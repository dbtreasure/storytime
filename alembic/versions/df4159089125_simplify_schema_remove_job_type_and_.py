"""simplify schema remove job type and source type

Revision ID: df4159089125
Revises: 2411eb0df3d9
Create Date: 2025-06-13 23:26:03.217758

"""

import contextlib
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "df4159089125"
down_revision: str | None = "2411eb0df3d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    # Remove columns that are no longer needed in simplified system
    if connection.dialect.has_table(connection, "jobs"):
        # Drop the index on job_type before dropping the column
        with contextlib.suppress(Exception):
            op.drop_index("ix_jobs_job_type", table_name="jobs")

        # Drop the book_id index and foreign key
        with contextlib.suppress(Exception):
            op.drop_index("ix_jobs_book_id", table_name="jobs")

        # Drop foreign key constraint for book_id
        with contextlib.suppress(Exception):
            op.drop_constraint("jobs_book_id_fkey", "jobs", type_="foreignkey")

        # Drop the simplified columns
        with contextlib.suppress(Exception):
            op.drop_column("jobs", "job_type")

        with contextlib.suppress(Exception):
            op.drop_column("jobs", "source_type")

        with contextlib.suppress(Exception):
            op.drop_column("jobs", "book_id")

    # Drop unused enum types
    with contextlib.suppress(Exception):
        connection.execute(sa.text("DROP TYPE IF EXISTS jobtype"))

    with contextlib.suppress(Exception):
        connection.execute(sa.text("DROP TYPE IF EXISTS sourcetype"))


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()

    # Re-create the enum types
    op.execute(
        sa.text("""
        CREATE TYPE IF NOT EXISTS jobtype AS ENUM (
            'SINGLE_VOICE', 'MULTI_VOICE', 'BOOK_PROCESSING', 'CHAPTER_PARSING'
        )
    """)
    )

    op.execute(
        sa.text("""
        CREATE TYPE IF NOT EXISTS sourcetype AS ENUM (
            'BOOK', 'CHAPTER', 'TEXT'
        )
    """)
    )

    # Re-add the columns
    if connection.dialect.has_table(connection, "jobs"):
        op.add_column("jobs", sa.Column("book_id", sa.String(), nullable=True))
        op.add_column(
            "jobs",
            sa.Column(
                "job_type",
                sa.Enum(
                    "SINGLE_VOICE",
                    "MULTI_VOICE",
                    "BOOK_PROCESSING",
                    "CHAPTER_PARSING",
                    name="jobtype",
                ),
                nullable=True,
            ),
        )
        op.add_column(
            "jobs",
            sa.Column(
                "source_type", sa.Enum("BOOK", "CHAPTER", "TEXT", name="sourcetype"), nullable=True
            ),
        )

        # Re-create indexes
        with contextlib.suppress(Exception):
            op.create_index("ix_jobs_book_id", "jobs", ["book_id"], unique=False)

        with contextlib.suppress(Exception):
            op.create_index("ix_jobs_job_type", "jobs", ["job_type"], unique=False)
