import re
import secrets
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import func

from .extensions import db
from .models import Lead, LeadActivity, Payment, Project, QuoteRevision

STAGES = [
    "Prospecting",
    "Qualification",
    "Need Analysis",
    "Value Proposition",
    "Decision Makers",
    "Negotiation & Payment",
    "Closed Won",
]
LOST_REASONS = {"Budget", "Competitor", "Unresponsive", "Infeasible", "Other"}
PAYMENT_METHODS = {"Cash", "UPI", "Bank Transfer", "Cheque"}
PROJECT_STATUSES = {"Not Started", "In Progress", "On Hold", "Completed", "Cancelled"}


class DomainError(ValueError):
    pass


def money(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise DomainError("Enter a valid monetary amount.")
    if not amount.is_finite():
        raise DomainError("Enter a valid monetary amount.")
    return amount


def normalize_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if not 7 <= len(digits) <= 15:
        raise DomainError("Enter a valid phone number.")
    return digits


def make_reference(prefix, model):
    # Random references plus unique constraints; callers retry on the rare collision.
    for _ in range(8):
        ref = f"{prefix}-{datetime.now(UTC):%y%m%d}-{secrets.token_hex(3).upper()}"
        if not model.query.filter_by(reference=ref).first():
            return ref
    raise DomainError("Unable to allocate a reference. Please retry.")


def record_activity(lead, action, actor=None, details=None):
    db.session.add(
        LeadActivity(
            lead=lead,
            actor_id=getattr(actor, "id", None),
            action=action,
            details=details or {},
        )
    )


def create_lead(data, actor=None, source="Web"):
    from .models import Service

    name, phone, location = (
        data.get(k, "").strip() for k in ("full_name", "phone", "location")
    )
    if not name or len(name) > 160:
        raise DomainError("Full name is required.")
    if not location or len(location) > 240:
        raise DomainError("Location is required.")
    normalized = normalize_phone(phone)
    email = (data.get("email") or "").strip().lower() or None
    if email and (
        len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
    ):
        raise DomainError("Enter a valid email address.")
    service = (
        db.session.get(Service, int(data.get("service_id", 0)))
        if str(data.get("service_id", "")).isdigit()
        else None
    )
    if not service or not service.active or service.archived:
        raise DomainError("Select an available service.")
    # Keep repeat enquiries as separate records. Flag a possible match for an
    # administrator instead of silently merging customer submissions.
    possible_duplicate = (
        Lead.query.filter(
            Lead.normalized_phone == normalized,
            Lead.status == "Open",
        )
        .order_by(Lead.created_at.desc())
        .first()
    )
    lead = Lead(
        reference=make_reference("F360", Lead),
        source=source,
        full_name=name,
        phone=phone.strip(),
        normalized_phone=normalized,
        email=email,
        location=location,
        service=service,
        service_name_snapshot=service.name,
        description=(data.get("description") or "").strip()[:5000] or None,
        created_by_id=getattr(actor, "id", None),
    )
    db.session.add(lead)
    db.session.flush()
    details = {"source": source, "service": service.name}
    if possible_duplicate:
        details["possible_duplicate_reference"] = possible_duplicate.reference
    record_activity(lead, "Lead created", actor, details)
    db.session.commit()
    return lead


def update_stage_data(lead, values, actor, *, allow_closed=False):
    if not allow_closed:
        ensure_open(lead)
    data = dict(lead.stage_data or {})
    if (
        lead.quote_approved
        and "approved_scope" in values
        and str(values["approved_scope"] or "").strip()
        != data.get("approved_scope", "")
    ):
        raise DomainError(
            "Approved scope is locked. Use the audited quote revision workflow first."
        )
    for key, val in values.items():
        if isinstance(val, str):
            val = val.strip()
        data[key] = val
    lead.stage_data = data
    record_activity(
        lead, "Lead details updated", actor, {"fields": sorted(values.keys())}
    )
    db.session.commit()


def ensure_open(lead):
    if lead.status != "Open":
        raise DomainError("Closed leads are locked.")


def transition(lead, target, actor):
    ensure_open(lead)
    if target not in STAGES:
        raise DomainError("Unknown lifecycle stage.")
    if target == "Closed Won":
        return close_won(lead, actor)
    if STAGES.index(target) != STAGES.index(lead.stage) + 1:
        raise DomainError("Lead stages must advance one step at a time.")
    data = lead.stage_data or {}
    required = {
        "Qualification": ["customer_need", "how_we_help", "project_scale"],
        "Need Analysis": ["client_goals", "analysis_notes"],
        "Value Proposition": ["value_statement"],
        "Decision Makers": ["decision_notes", "approved_scope", "feasibility"],
    }
    missing = [
        k.replace("_", " ") for k in required.get(lead.stage, []) if not data.get(k)
    ]
    if missing:
        raise DomainError(
            "Complete required fields before advancing: " + ", ".join(missing)
        )
    if lead.stage == "Decision Makers" and not lead.quote_approved:
        raise DomainError("Approve the quote and scope before advancing.")
    if lead.stage == "Value Proposition" and lead.quoted_price <= 0:
        raise DomainError("Enter a base quoted price before advancing.")
    lead.stage = target
    record_activity(
        lead,
        "Stage changed",
        actor,
        {"from": STAGES[STAGES.index(target) - 1], "to": target},
    )
    db.session.commit()
    return lead


def save_quote(
    lead,
    base_price,
    discount="0",
    notes="",
    actor=None,
    approve=False,
    revise=False,
    approved_scope=None,
):
    ensure_open(lead)
    if lead.stage not in {
        "Value Proposition",
        "Decision Makers",
        "Negotiation & Payment",
    }:
        raise DomainError("Quotes can only be managed from Value Proposition onward.")
    if approve and lead.stage not in {"Decision Makers", "Negotiation & Payment"}:
        raise DomainError(
            "Approve the quote during Decision Makers after recording the scope."
        )
    if lead.quote_approved and (
        money(base_price) != lead.quoted_price
        or money(discount) != lead.discount_amount
    ):
        if not revise:
            raise DomainError(
                "Approved quote is locked. Select the audited revision option to revise it."
            )
        lead.quote_approved = False
        record_activity(
            lead,
            "Approved quote revision opened",
            actor,
            {"previous_final": str(lead.final_price)},
        )
    if revise and approved_scope is not None:
        revised = dict(lead.stage_data or {})
        revised["approved_scope"] = str(approved_scope).strip()[:10000]
        lead.stage_data = revised
    base, reduction = money(base_price), money(discount)
    if base < 0 or reduction < 0 or reduction > base:
        raise DomainError("Discount must be between zero and the quoted amount.")
    total = base - reduction
    if lead.stage == "Negotiation & Payment" and revise:
        if base == lead.quoted_price and reduction == lead.discount_amount:
            raise DomainError("Change the quote amount to record a negotiated price revision.")
        if total < recorded_payment_total(lead):
            raise DomainError(
                "The new agreed total cannot be less than payments already recorded."
            )
    lead.quoted_price, lead.discount_amount, lead.final_price = base, reduction, total
    if approve:
        if not (lead.stage_data or {}).get("approved_scope"):
            raise DomainError("Approved scope is required.")
        lead.quote_approved = True
    was_revised = bool(lead.quote_revisions)
    db.session.add(
        QuoteRevision(
            lead=lead,
            base_price=base,
            discount_amount=reduction,
            final_price=total,
            notes=notes[:2000] or None,
            actor_id=getattr(actor, "id", None),
        )
    )
    action = "Quote revised" if was_revised else "Quote created"
    record_activity(
        lead,
        action,
        actor,
        {
            "base": str(base),
            "discount": str(reduction),
            "final": str(total),
            "approved": approve,
            "revision_authorized": revise,
        },
    )
    db.session.commit()
    return lead


def ensure_payment_allowed(lead):
    if lead.status == "Open":
        return
    if (
        lead.status == "Closed Won"
        and lead.project
        and lead.project.status != "Cancelled"
    ):
        return
    raise DomainError("Payments can only be managed for active leads or active won projects.")


def recorded_payment_total(lead):
    total = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter_by(lead_id=lead.id)
        .scalar()
    )
    return Decimal(str(total))


def verified_payment_total(lead):
    total = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter_by(lead_id=lead.id, verified=True)
        .scalar()
    )
    return Decimal(str(total))


def sync_project_payment_summary(lead):
    if lead.project:
        lead.project.verified_payment_summary = verified_payment_total(lead)


def record_payment(lead, amount, method, received_on, actor, reference="", notes=""):
    ensure_payment_allowed(lead)
    value = money(amount)
    if value <= 0 or method not in PAYMENT_METHODS:
        raise DomainError("Use a positive amount and a supported payment method.")
    if lead.final_price > 0 and recorded_payment_total(lead) + value > lead.final_price:
        raise DomainError("This payment is greater than the remaining agreed balance.")
    payment = Payment(
        lead=lead,
        amount=value,
        method=method,
        reference=reference[:120] or None,
        received_on=received_on,
        notes=notes[:2000] or None,
        created_by_id=actor.id,
    )
    db.session.add(payment)
    record_activity(
        lead, "Payment recorded", actor, {"amount": str(value), "method": method}
    )
    db.session.commit()
    return payment


def verify_payment(payment, actor):
    ensure_payment_allowed(payment.lead)
    if payment.verified:
        raise DomainError("Payment is already verified.")
    payment.verified, payment.verified_by_id, payment.verified_at = (
        True,
        actor.id,
        datetime.now(UTC),
    )
    record_activity(
        payment.lead,
        "Payment verified",
        actor,
        {"payment_id": payment.id, "amount": str(payment.amount)},
    )
    sync_project_payment_summary(payment.lead)
    db.session.commit()
    return payment


def close_lost(lead, reason, notes, actor):
    ensure_open(lead)
    if reason not in LOST_REASONS:
        raise DomainError("Choose a valid Closed Lost reason.")
    lead.status, lead.closed_reason, lead.closed_notes = (
        "Closed Lost",
        reason,
        (notes or "").strip()[:2000] or None,
    )
    lead.closed_by_id, lead.closed_at = actor.id, datetime.now(UTC)
    record_activity(lead, "Closed Lost", actor, {"reason": reason})
    db.session.commit()
    return lead


def reopen_lost(lead, actor):
    if lead.status != "Closed Lost":
        raise DomainError("Only leads closed as Lost can be reopened.")
    closed_details = {
        "reason": lead.closed_reason,
        "notes": lead.closed_notes,
        "closed_at": lead.closed_at.isoformat() if lead.closed_at else None,
    }
    lead.status = "Open"
    lead.closed_reason = None
    lead.closed_notes = None
    lead.closed_by_id = None
    lead.closed_at = None
    record_activity(lead, "Lead reopened", actor, closed_details)
    db.session.commit()
    return lead


def close_won(lead, actor):
    ensure_open(lead)
    if lead.stage != "Negotiation & Payment":
        raise DomainError("Complete the lifecycle stages before closing Won.")
    if not lead.quote_approved or not (lead.stage_data or {}).get("approved_scope"):
        raise DomainError("An approved quote and scope are required.")
    if lead.final_price <= 0:
        raise DomainError("Final agreed value must be greater than zero.")
    paid = verified_payment_total(lead)
    if paid <= 0:
        raise DomainError(
            "Verify the customer's initial or token payment before creating the project."
        )
    try:
        lead.status, lead.stage, lead.closed_by_id, lead.closed_at = (
            "Closed Won",
            "Closed Won",
            actor.id,
            datetime.now(UTC),
        )
        project = Project(
            reference=make_reference("PRJ", Project),
            lead=lead,
            client_name=lead.full_name,
            client_phone=lead.phone,
            client_email=lead.email,
            client_location=lead.location,
            approved_services=lead.service_name_snapshot,
            approved_scope=(lead.stage_data or {}).get("approved_scope", ""),
            deliverables=(lead.stage_data or {}).get("deliverables"),
            final_value=lead.final_price,
            verified_payment_summary=paid,
        )
        db.session.add(project)
        db.session.flush()
        record_activity(
            lead,
            "Closed Won and project created",
            actor,
            {"project_reference": project.reference},
        )
        db.session.commit()
        return project
    except Exception:
        db.session.rollback()
        raise
