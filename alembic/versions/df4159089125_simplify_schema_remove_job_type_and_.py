"""simplify schema remove job type and source type

Revision ID: df4159089125
Revises: 2411eb0df3d9
Create Date: 2025-06-13 23:26:03.217758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df4159089125'
down_revision: Union[str, None] = '2411eb0df3d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    
    # Remove columns that are no longer needed in simplified system
    if connection.dialect.has_table(connection, "jobs"):
        # Drop the index on job_type before dropping the column
        try:
            op.drop_index("ix_jobs_job_type", table_name="jobs")
        except Exception:
            pass  # Index might not exist
        
        # Drop the book_id index and foreign key
        try:
            op.drop_index("ix_jobs_book_id", table_name="jobs")
        except Exception:
            pass
            
        # Drop foreign key constraint for book_id
        try:
            op.drop_constraint("jobs_book_id_fkey", "jobs", type_="foreignkey")
        except Exception:
            pass
        
        # Drop the simplified columns
        try:
            op.drop_column("jobs", "job_type")
        except Exception:
            pass
            
        try:
            op.drop_column("jobs", "source_type")  
        except Exception:
            pass
            
        try:
            op.drop_column("jobs", "book_id")
        except Exception:
            pass
    
    # Drop unused enum types
    try:
        connection.execute(sa.text("DROP TYPE IF EXISTS jobtype"))
    except Exception:
        pass
        
    try:
        connection.execute(sa.text("DROP TYPE IF EXISTS sourcetype"))
    except Exception:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()
    
    # Re-create the enum types
    op.execute(sa.text("""
        CREATE TYPE IF NOT EXISTS jobtype AS ENUM (
            'SINGLE_VOICE', 'MULTI_VOICE', 'BOOK_PROCESSING', 'CHAPTER_PARSING'
        )
    """))
    
    op.execute(sa.text("""
        CREATE TYPE IF NOT EXISTS sourcetype AS ENUM (
            'BOOK', 'CHAPTER', 'TEXT'
        )
    """))
    
    # Re-add the columns
    if connection.dialect.has_table(connection, "jobs"):
        op.add_column("jobs", sa.Column("book_id", sa.String(), nullable=True))
        op.add_column("jobs", sa.Column("job_type", sa.Enum("SINGLE_VOICE", "MULTI_VOICE", "BOOK_PROCESSING", "CHAPTER_PARSING", name="jobtype"), nullable=True))
        op.add_column("jobs", sa.Column("source_type", sa.Enum("BOOK", "CHAPTER", "TEXT", name="sourcetype"), nullable=True))
        
        # Re-create indexes
        try:
            op.create_index("ix_jobs_book_id", "jobs", ["book_id"], unique=False)
        except Exception:
            pass
            
        try:
            op.create_index("ix_jobs_job_type", "jobs", ["job_type"], unique=False)
        except Exception:
            pass
