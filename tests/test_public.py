from app.models import Lead, PortfolioItem, Service
from app.extensions import db


def test_home_and_active_services(client, app):
    with app.app_context():
        db.session.add(Service(name="Inactive", slug="inactive", active=False))
        db.session.commit()
    response = client.get("/")
    assert (
        response.status_code == 200
        and b"Garden" in response.data
        and b"Inactive" not in response.data
    )


def test_unpublished_portfolio_hidden(client, app):
    with app.app_context():
        db.session.add(
            PortfolioItem(
                title="Private garden", description="Not public", published=False
            )
        )
        db.session.commit()
    assert b"Private garden" not in client.get("/our-work").data


def test_valid_enquiry_creates_lead(client, app):
    with app.app_context():
        service = Service.query.filter_by(slug="garden").first()
        sid = service.id
    response = client.post(
        "/enquire",
        data={
            "full_name": "A Person",
            "phone": "+91 98765 43210",
            "location": "Pune",
            "service_id": sid,
        },
    )
    assert response.status_code == 302
    with app.app_context():
        lead = Lead.query.one()
        assert (
            lead.status == "Open"
            and lead.stage == "Prospecting"
            and lead.source == "Web"
        )


def test_invalid_enquiry_does_not_create_lead(client, app):
    response = client.post(
        "/enquire",
        data={"full_name": "", "phone": "bad", "location": "", "service_id": "999"},
    )
    assert response.status_code == 200
    with app.app_context():
        assert Lead.query.count() == 0
