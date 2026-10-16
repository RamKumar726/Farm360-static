"""Initial FARM360 schema.

Revision ID: 0001_initial
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_user_email", "admin_user", ["email"], unique=True)
    op.create_table(
        "service",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False, unique=True),
        sa.Column("short_description", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("image_key", sa.String(255)),
        sa.Column("benefits", sa.Text()),
        sa.Column("features", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(120), nullable=False),
        sa.Column("introduction", sa.Text(), nullable=False),
        sa.Column("mission", sa.Text(), nullable=False),
        sa.Column("vision", sa.Text(), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("address", sa.String(300), nullable=False),
        sa.Column("social_links", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "lead",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(24), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("normalized_phone", sa.String(40), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("location", sa.String(240), nullable=False),
        sa.Column(
            "service_id", sa.Integer(), sa.ForeignKey("service.id", ondelete="SET NULL")
        ),
        sa.Column("service_name_snapshot", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stage_data", sa.JSON(), nullable=False),
        sa.Column("quoted_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("final_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quote_approved", sa.Boolean(), nullable=False),
        sa.Column("closed_reason", sa.String(32)),
        sa.Column("closed_notes", sa.Text()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("admin_user.id")),
        sa.Column("closed_by_id", sa.Integer(), sa.ForeignKey("admin_user.id")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quoted_price >= 0", name="ck_lead_quote_nonnegative"),
        sa.CheckConstraint(
            "discount_amount >= 0 AND discount_amount <= quoted_price",
            name="ck_lead_discount_valid",
        ),
        sa.CheckConstraint(
            "final_price = quoted_price - discount_amount",
            name="ck_lead_final_matches_quote",
        ),
    )
    for col in ("normalized_phone", "stage", "status", "created_at"):
        op.create_index(f"ix_lead_{col}", "lead", [col], unique=False)
    op.create_index("ix_lead_reference", "lead", ["reference"], unique=True)
    op.create_index("ix_lead_phone", "lead", ["phone"], unique=False)
    op.create_table(
        "portfolio_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "service_id", sa.Integer(), sa.ForeignKey("service.id", ondelete="SET NULL")
        ),
        sa.Column("location", sa.String(180)),
        sa.Column("image_key", sa.String(255)),
        sa.Column("gallery", sa.JSON(), nullable=False),
        sa.Column("completed_on", sa.Date()),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "lead_activity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("lead.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("admin_user.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lead_activity_lead_id", "lead_activity", ["lead_id"])
    op.create_table(
        "quote_revision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("lead.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("final_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("admin_user.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_quote_revision_lead_id", "quote_revision", ["lead_id"])
    op.create_table(
        "payment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("lead.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.String(24), nullable=False),
        sa.Column("reference", sa.String(120)),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("verified_by_id", sa.Integer(), sa.ForeignKey("admin_user.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("admin_user.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
    )
    op.create_index("ix_payment_lead_id", "payment", ["lead_id"])
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(24), nullable=False),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("lead.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("client_name", sa.String(160), nullable=False),
        sa.Column("client_phone", sa.String(40), nullable=False),
        sa.Column("client_email", sa.String(254)),
        sa.Column("client_location", sa.String(240), nullable=False),
        sa.Column("approved_services", sa.String(300), nullable=False),
        sa.Column("approved_scope", sa.Text(), nullable=False),
        sa.Column("deliverables", sa.Text()),
        sa.Column("final_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("verified_payment_summary", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date()),
        sa.Column("target_completion_date", sa.Date()),
        sa.Column("internal_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("final_value >= 0", name="ck_project_value_nonnegative"),
        sa.UniqueConstraint("lead_id", name="uq_project_lead"),
    )
    op.create_index("ix_project_reference", "project", ["reference"], unique=True)
    op.create_index("ix_project_status", "project", ["status"])


def downgrade():
    op.drop_table("project")
    op.drop_table("payment")
    op.drop_table("quote_revision")
    op.drop_table("lead_activity")
    op.drop_table("portfolio_item")
    op.drop_table("lead")
    op.drop_table("site_settings")
    op.drop_table("service")
    op.drop_table("admin_user")
