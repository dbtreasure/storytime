"""add_vector_store_tables

Revision ID: c181b831cfcc
Revises: 9fdc7d737873
Create Date: 2025-06-24 18:28:02.994104

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c181b831cfcc"
down_revision: str | None = "9fdc7d737873"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create user_vector_stores table
    op.create_table(
        "user_vector_stores",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("openai_vector_store_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="unique_user_vector_store"),
    )
    op.create_index(
        op.f("ix_user_vector_stores_user_id"), "user_vector_stores", ["user_id"], unique=False
    )

    # Create vector_store_files table
    op.create_table(
        "vector_store_files",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_vector_store_id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("openai_file_id", sa.String(), nullable=False),
        sa.Column("file_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_vector_store_id"], ["user_vector_stores.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vector_store_files_job_id"), "vector_store_files", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_vector_store_files_user_vector_store_id"),
        "vector_store_files",
        ["user_vector_store_id"],
        unique=False,
    )

    # Add vector_store_file_id column to jobs table
    op.add_column("jobs", sa.Column("vector_store_file_id", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove vector_store_file_id column from jobs table
    op.drop_column("jobs", "vector_store_file_id")

    # Drop vector_store_files table
    op.drop_index(
        op.f("ix_vector_store_files_user_vector_store_id"), table_name="vector_store_files"
    )
    op.drop_index(op.f("ix_vector_store_files_job_id"), table_name="vector_store_files")
    op.drop_table("vector_store_files")

    # Drop user_vector_stores table
    op.drop_index(op.f("ix_user_vector_stores_user_id"), table_name="user_vector_stores")
    op.drop_table("user_vector_stores")
