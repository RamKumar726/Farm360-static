from datetime import datetime, timezone
from decimal import Decimal
from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint
from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        return self.active


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(AdminUser, int(user_id))
    except (TypeError, ValueError):
        return None


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    short_description = db.Column(db.String(300), nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    image_key = db.Column(db.String(255))
    benefits = db.Column(db.Text)
    features = db.Column(db.Text)
    active = db.Column(db.Boolean, nullable=False, default=True)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class PortfolioItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    service_id = db.Column(db.Integer, db.ForeignKey("service.id", ondelete="SET NULL"))
    location = db.Column(db.String(180))
    image_key = db.Column(db.String(255))
    gallery = db.Column(db.JSON, nullable=False, default=list)
    completed_on = db.Column(db.Date)
    published = db.Column(db.Boolean, nullable=False, default=False)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    service = db.relationship(Service)


class SiteSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120), nullable=False, default="FARM360")
    introduction = db.Column(
        db.Text,
        nullable=False,
        default="Agricultural and gardening services shaped around your land and growing goals.",
    )
    mission = db.Column(db.Text, nullable=False, default="")
    vision = db.Column(db.Text, nullable=False, default="")
    phone = db.Column(db.String(40), nullable=False, default="")
    email = db.Column(db.String(254), nullable=False, default="")
    address = db.Column(db.String(300), nullable=False, default="")
    social_links = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class Lead(db.Model):
    __table_args__ = (
        CheckConstraint("quoted_price >= 0", name="ck_lead_quote_nonnegative"),
        CheckConstraint(
            "discount_amount >= 0 AND discount_amount <= quoted_price",
            name="ck_lead_discount_valid",
        ),
        CheckConstraint(
            "final_price = quoted_price - discount_amount",
            name="ck_lead_final_matches_quote",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(24), unique=True, nullable=False, index=True)
    source = db.Column(db.String(20), nullable=False, default="Web")
    full_name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=False, index=True)
    normalized_phone = db.Column(db.String(40), nullable=False, index=True)
    email = db.Column(db.String(254))
    location = db.Column(db.String(240), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id", ondelete="SET NULL"))
    service_name_snapshot = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    stage = db.Column(db.String(32), nullable=False, default="Prospecting", index=True)
    status = db.Column(db.String(20), nullable=False, default="Open", index=True)
    stage_data = db.Column(db.JSON, nullable=False, default=dict)
    quoted_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    discount_amount = db.Column(
        db.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    final_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    quote_approved = db.Column(db.Boolean, nullable=False, default=False)
    closed_reason = db.Column(db.String(32))
    closed_notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("admin_user.id"))
    closed_by_id = db.Column(db.Integer, db.ForeignKey("admin_user.id"))
    closed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    service = db.relationship(Service)
    activities = db.relationship(
        "LeadActivity",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="LeadActivity.created_at",
    )
    payments = db.relationship(
        "Payment",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="Payment.created_at",
    )
    quote_revisions = db.relationship(
        "QuoteRevision",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="QuoteRevision.created_at",
    )
    project = db.relationship("Project", back_populates="lead", uselist=False)


class LeadActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(
        db.Integer,
        db.ForeignKey("lead.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id = db.Column(db.Integer, db.ForeignKey("admin_user.id"))
    action = db.Column(db.String(80), nullable=False)
    details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    actor = db.relationship(AdminUser)
    lead = db.relationship(Lead, back_populates="activities")


class QuoteRevision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(
        db.Integer,
        db.ForeignKey("lead.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_price = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False)
    final_price = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.Text)
    actor_id = db.Column(db.Integer, db.ForeignKey("admin_user.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    lead = db.relationship(Lead, back_populates="quote_revisions")


class Payment(db.Model):
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_amount_positive"),)
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(
        db.Integer,
        db.ForeignKey("lead.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    method = db.Column(db.String(24), nullable=False)
    reference = db.Column(db.String(120))
    received_on = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    verified_by_id = db.Column(db.Integer, db.ForeignKey("admin_user.id"))
    verified_at = db.Column(db.DateTime(timezone=True))
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("admin_user.id"), nullable=False
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    lead = db.relationship(Lead, back_populates="payments")


class Project(db.Model):
    __table_args__ = (
        UniqueConstraint("lead_id", name="uq_project_lead"),
        CheckConstraint("final_value >= 0", name="ck_project_value_nonnegative"),
    )
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(24), unique=True, nullable=False, index=True)
    lead_id = db.Column(
        db.Integer, db.ForeignKey("lead.id", ondelete="RESTRICT"), nullable=False
    )
    client_name = db.Column(db.String(160), nullable=False)
    client_phone = db.Column(db.String(40), nullable=False)
    client_email = db.Column(db.String(254))
    client_location = db.Column(db.String(240), nullable=False)
    approved_services = db.Column(db.String(300), nullable=False)
    approved_scope = db.Column(db.Text, nullable=False)
    deliverables = db.Column(db.Text)
    final_value = db.Column(db.Numeric(12, 2), nullable=False)
    verified_payment_summary = db.Column(
        db.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    status = db.Column(db.String(20), nullable=False, default="Not Started", index=True)
    start_date = db.Column(db.Date)
    target_completion_date = db.Column(db.Date)
    internal_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    lead = db.relationship(Lead, back_populates="project")
    updates = db.relationship(
        "ProjectUpdate",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectUpdate.created_at.desc()",
    )


class ProjectUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id = db.Column(db.Integer, db.ForeignKey("admin_user.id"))
    title = db.Column(db.String(180), nullable=False)
    notes = db.Column(db.Text)
    images = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    project = db.relationship(Project, back_populates="updates")
    created_by = db.relationship(AdminUser)
