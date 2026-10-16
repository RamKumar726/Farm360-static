import pytest
from app.services import (
    DomainError,
    close_lost,
    create_lead,
    money,
    normalize_phone,
    transition,
)


def make_lead():
    return create_lead(
        {
            "full_name": "Client",
            "phone": "9876543210",
            "location": "Pune",
            "service_id": "1",
        }
    )


def test_invalid_stage_transition(app):
    with app.app_context():
        lead = make_lead()
        with pytest.raises(DomainError):
            transition(lead, "Need Analysis", None)


def test_closed_lost_requires_valid_reason_and_locks(app):
    with app.app_context():
        lead = make_lead()
        with pytest.raises(DomainError):
            close_lost(lead, "", "", None)
        from app.models import AdminUser

        admin = AdminUser.query.first()
        close_lost(lead, "Budget", "", admin)
        with pytest.raises(DomainError):
            transition(lead, "Qualification", admin)


def test_phone_and_decimal(app):
    assert normalize_phone("+91 (98765) 43210") == "919876543210"
    assert str(money("100.105")) == "100.11"


def test_required_fields_are_enforced(app):
    with app.app_context():
        with pytest.raises(DomainError):
            create_lead(
                {
                    "full_name": "",
                    "phone": "9876543210",
                    "location": "X",
                    "service_id": "1",
                }
            )
