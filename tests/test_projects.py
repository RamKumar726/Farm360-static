import pytest
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import AdminUser, Project
from app.services import (
    close_won,
    create_lead,
    record_payment,
    save_quote,
    transition,
    update_stage_data,
    verify_payment,
)


def test_project_one_to_one_constraint(app):
    with app.app_context():
        from app.models import Lead, Service

        lead = Lead(
            reference="F360-TEST",
            full_name="Client",
            phone="9876543210",
            normalized_phone="9876543210",
            location="Pune",
            service_name_snapshot="Garden",
            service_id=Service.query.first().id,
        )
        db.session.add(lead)
        db.session.flush()

        def project(ref):
            return Project(
                reference=ref,
                lead_id=lead.id,
                client_name="Client",
                client_phone="9876543210",
                client_location="Pune",
                approved_services="Garden",
                approved_scope="Scope",
                final_value=1,
            )

        db.session.add(project("PRJ-ONE"))
        db.session.commit()
        db.session.add(project("PRJ-TWO"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_closed_won_creates_exactly_one_project(app):
    from datetime import date

    with app.app_context():
        admin = AdminUser.query.first()
        lead = create_lead(
            {
                "full_name": "Client",
                "phone": "9876543210",
                "location": "Pune",
                "service_id": "1",
            }
        )
        transition(lead, "Qualification", admin)
        update_stage_data(
            lead,
            {
                "customer_need": "Home garden",
                "how_we_help": "Garden planning",
                "project_scale": "Small",
            },
            admin,
        )
        transition(lead, "Need Analysis", admin)
        update_stage_data(
            lead,
            {"client_goals": "Grow vegetables", "analysis_notes": "Sunny terrace"},
            admin,
        )
        transition(lead, "Value Proposition", admin)
        update_stage_data(lead, {"value_statement": "A garden plan"}, admin)
        save_quote(lead, "1000.00", "100.00", actor=admin)
        transition(lead, "Decision Makers", admin)
        update_stage_data(
            lead,
            {
                "decision_notes": "Customer approved",
                "approved_scope": "Plan and install garden",
                "feasibility": "Feasible",
            },
            admin,
        )
        save_quote(lead, "1000.00", "100.00", actor=admin, approve=True)
        transition(lead, "Negotiation & Payment", admin)
        payment = record_payment(lead, "900.00", "UPI", date.today(), admin)
        verify_payment(payment, admin)

        project = close_won(lead, admin)
        assert lead.status == "Closed Won"
        assert project.lead_id == lead.id
        assert Project.query.filter_by(lead_id=lead.id).count() == 1
        with pytest.raises(Exception):
            close_won(lead, admin)
        assert Project.query.filter_by(lead_id=lead.id).count() == 1
