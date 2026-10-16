def test_admin_requires_login(client):
    assert client.get("/admin/").status_code == 302


def test_invalid_login_rejected(client):
    assert (
        client.post(
            "/login", data={"email": "admin@example.com", "password": "wrong"}
        ).status_code
        == 200
    )
    assert client.get("/admin/").status_code == 302


def test_logout(client):
    client.post(
        "/login", data={"email": "admin@example.com", "password": "long-test-password"}
    )
    client.post("/logout")
    assert client.get("/admin/").status_code == 302


def test_no_public_registration(client):
    assert client.get("/register").status_code == 404


def test_admin_pages_render(admin_client):
    for path in (
        "/admin/",
        "/admin/services",
        "/admin/portfolio",
        "/admin/settings",
        "/admin/projects",
        "/admin/leads",
    ):
        assert admin_client.get(path).status_code == 200


def test_lead_detail_displays_seven_step_journey(client, app):
    from app.services import create_lead

    with app.app_context():
        lead = create_lead(
            {
                "full_name": "Journey Client",
                "phone": "9876543210",
                "location": "Pune",
                "service_id": "1",
            }
        )
        lead_id = lead.id
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "long-test-password"},
    )
    response = client.get(f"/admin/leads/{lead_id}")
    assert response.status_code == 200
    assert b"LEAD JOURNEY" in response.data
    assert b"In progress" in response.data
    assert b"Negotiation &amp; Payment" in response.data


def test_save_and_continue_persists_qualification_before_advancing(client, app):
    from app.extensions import db
    from app.models import Lead
    from app.services import create_lead

    with app.app_context():
        lead = create_lead(
            {
                "full_name": "Journey Client",
                "phone": "9876543210",
                "location": "Pune",
                "service_id": "1",
            }
        )
        lead_id = lead.id
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "long-test-password"},
    )
    client.post(
        f"/admin/leads/{lead_id}/advance",
        data={"stage": "Qualification"},
    )
    response = client.post(
        f"/admin/leads/{lead_id}/advance",
        data={
            "stage": "Need Analysis",
            "customer_need": "A terrace vegetable garden",
            "how_we_help": "Plan and install a garden",
            "project_scale": "Small",
            "land_area": "500 sq ft",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        lead = db.session.get(Lead, lead_id)
        assert lead.stage == "Need Analysis"
        assert lead.stage_data["customer_need"] == "A terrace vegetable garden"


def test_closed_lead_stage_can_be_reviewed_and_edited_with_audit_trail(client, app):
    from app.extensions import db
    from app.models import AdminUser, Lead
    from app.services import create_lead, transition

    with app.app_context():
        lead = create_lead(
            {
                "full_name": "Closed Client",
                "phone": "9876543210",
                "location": "Pune",
                "service_id": "1",
            }
        )
        lead_id = lead.id
        actor = AdminUser.query.first()
        transition(lead, "Qualification", actor)
        from app.services import close_lost

        close_lost(lead, "Unresponsive", "Client did not reply", actor)
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "long-test-password"},
    )
    response = client.get(f"/admin/leads/{lead_id}?edit_stage=1")
    assert response.status_code == 200
    assert b"REVIEW STEP" in response.data
    response = client.post(
        f"/admin/leads/{lead_id}/details",
        data={"customer_need": "Edited after closure"},
    )
    assert response.status_code == 302
    with app.app_context():
        lead = db.session.get(Lead, lead_id)
        assert lead.status == "Closed Lost"
        assert lead.stage_data["customer_need"] == "Edited after closure"
        assert lead.activities[-1].action == "Lead details updated"
