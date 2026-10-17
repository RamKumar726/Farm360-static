"""Add project progress updates with image references.

Revision ID: 0002_project_updates
Revises: 0001_initial
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_project_updates"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_update",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_update_project_id", "project_update", ["project_id"]
    )


def downgrade():
    op.drop_index("ix_project_update_project_id", table_name="project_update")
    op.drop_table("project_update")
