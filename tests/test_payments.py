import pytest
from app.models import AdminUser
from app.services import (
    DomainError,
    create_lead,
    record_payment,
    save_quote,
    verify_payment,
)


def test_reject_negative_discount(app):
    with app.app_context():
        lead = create_lead(
            {
                "full_name": "Client",
                "phone": "9876543210",
                "location": "Pune",
                "service_id": "1",
            }
        )
        with pytest.raises(DomainError):
            save_quote(lead, "100", "-1", actor=AdminUser.query.first())


def test_payment_requires_explicit_verification(app):
    with app.app_context():
        lead = create_lead(
            {
                "full_name": "Client",
                "phone": "9876543210",
                "location": "Pune",
                "service_id": "1",
            }
        )
        admin = AdminUser.query.first()
        payment = record_payment(
            lead, "20", "UPI", __import__("datetime").date.today(), admin
        )
        assert payment.verified is False
        verify_payment(payment, admin)
        assert payment.verified is True
