"""Add image galleries to services.

Revision ID: 0003_service_gallery
Revises: 0002_project_updates
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_service_gallery"
down_revision = "0002_project_updates"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "service",
        sa.Column(
            "gallery",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade():
    op.drop_column("service", "gallery")
