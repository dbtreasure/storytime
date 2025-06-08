"""add unified job management tables

Revision ID: 2411eb0df3d9
Revises: f4e761e08e6e
Create Date: 2025-06-07 19:59:47.447144

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2411eb0df3d9'
down_revision: str | None = 'f4e761e08e6e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    # Create jobs table with inline enum definitions
    # This will let PostgreSQL handle enum creation automatically
    if not connection.dialect.has_table(connection, 'jobs'):
        op.create_table(
            'jobs',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('book_id', sa.String(), nullable=True),
            sa.Column('job_type', sa.Enum('SINGLE_VOICE', 'MULTI_VOICE', 'BOOK_PROCESSING', 'CHAPTER_PARSING', name='jobtype'), nullable=False),
            sa.Column('source_type', sa.Enum('BOOK', 'CHAPTER', 'TEXT', name='sourcetype'), nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED', name='jobstatus'), nullable=False),
            sa.Column('progress', sa.Float(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('config', sa.JSON(), nullable=True),
            sa.Column('result_data', sa.JSON(), nullable=True),
            sa.Column('input_file_key', sa.String(), nullable=True),
            sa.Column('output_file_key', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['book_id'], ['book.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )

        # Create indexes for jobs table
        op.create_index(op.f('ix_jobs_book_id'), 'jobs', ['book_id'], unique=False)
        op.create_index(op.f('ix_jobs_created_at'), 'jobs', ['created_at'], unique=False)
        op.create_index(op.f('ix_jobs_job_type'), 'jobs', ['job_type'], unique=False)
        op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)
        op.create_index(op.f('ix_jobs_user_id'), 'jobs', ['user_id'], unique=False)

    # Create job_steps table if it doesn't exist
    if not connection.dialect.has_table(connection, 'job_steps'):
        op.create_table(
            'job_steps',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('job_id', sa.String(), nullable=False),
            sa.Column('step_name', sa.String(), nullable=False),
            sa.Column('step_order', sa.Integer(), nullable=False),
            sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', name='stepstatus'), nullable=False),
            sa.Column('progress', sa.Float(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('step_metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
            sa.PrimaryKeyConstraint('id')
        )

        # Create indexes for job_steps table
        op.create_index(op.f('ix_job_steps_job_id'), 'job_steps', ['job_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()

    # Drop tables if they exist
    if connection.dialect.has_table(connection, 'job_steps'):
        op.drop_index(op.f('ix_job_steps_job_id'), table_name='job_steps')
        op.drop_table('job_steps')

    if connection.dialect.has_table(connection, 'jobs'):
        op.drop_index(op.f('ix_jobs_user_id'), table_name='jobs')
        op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
        op.drop_index(op.f('ix_jobs_job_type'), table_name='jobs')
        op.drop_index(op.f('ix_jobs_created_at'), table_name='jobs')
        op.drop_index(op.f('ix_jobs_book_id'), table_name='jobs')
        op.drop_table('jobs')

    # Drop enum types using raw SQL
    connection.execute(sa.text("DROP TYPE IF EXISTS stepstatus"))
    connection.execute(sa.text("DROP TYPE IF EXISTS jobstatus"))
    connection.execute(sa.text("DROP TYPE IF EXISTS sourcetype"))
    connection.execute(sa.text("DROP TYPE IF EXISTS jobtype"))
