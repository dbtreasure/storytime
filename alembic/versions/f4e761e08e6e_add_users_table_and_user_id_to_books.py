"""Add users table and user_id to books

Revision ID: f4e761e08e6e
Revises: 2273b4060b15
Create Date: 2025-06-01 00:29:21.621276

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f4e761e08e6e'
down_revision: str | None = '2273b4060b15'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)

    # Add user_id column to book table
    op.add_column('book', sa.Column('user_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_book_user_id', 'book', 'users', ['user_id'], ['id'])

    # Note: In production, you'd want to populate user_id for existing books
    # or make it nullable temporarily and handle the migration


def downgrade() -> None:
    """Downgrade schema."""
    # Remove foreign key and user_id column from book table
    op.drop_constraint('fk_book_user_id', 'book', type_='foreignkey')
    op.drop_column('book', 'user_id')

    # Drop users table
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
