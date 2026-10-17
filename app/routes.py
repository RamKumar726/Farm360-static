import re
from datetime import date
from decimal import Decimal
from functools import wraps

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from werkzeug.security import check_password_hash

from .extensions import csrf, db, limiter
from .models import (
    AdminUser,
    Lead,
    LeadActivity,
    PortfolioItem,
    Project,
    ProjectUpdate,
    Service,
    SiteSettings,
)
from .services import (
    PROJECT_STATUSES,
    DomainError,
    close_lost,
    create_lead,
    record_payment,
    save_quote,
    transition,
    update_stage_data,
    verify_payment,
)
from .storage import UploadError, serve_local_image, store_image

public_bp = Blueprint("public", __name__)
auth_bp = Blueprint("auth", __name__)
admin_bp = Blueprint("admin", __name__)
api_bp = Blueprint("api", __name__)
STAGE_DATA_FIELDS = {
    "customer_need",
    "how_we_help",
    "project_scale",
    "land_area",
    "crop_type",
    "water_availability",
    "constraints",
    "qualification_notes",
    "challenges",
    "pest_challenges",
    "soil_challenges",
    "irrigation_challenges",
    "yield_challenges",
    "other_challenges",
    "client_goals",
    "current_practices",
    "analysis_notes",
    "value_statement",
    "expected_benefits",
    "roi_statement",
    "recommended_services",
    "decision_notes",
    "approved_scope",
    "feasibility",
    "verified_services",
    "deliverables",
}


def settings():
    obj = SiteSettings.query.first()
    if not obj:
        obj = SiteSettings()
        db.session.add(obj)
        db.session.commit()
    return obj


@public_bp.get("/")
def home():
    return render_template(
        "public/home.html",
        services=Service.query.filter_by(active=True, archived=False)
        .order_by(Service.display_order, Service.name)
        .all(),
        works=PortfolioItem.query.filter_by(published=True, archived=False)
        .order_by(PortfolioItem.display_order, PortfolioItem.created_at.desc())
        .limit(6)
        .all(),
        settings=settings(),
    )


@public_bp.get("/services")
def services_page():
    return render_template(
        "public/services.html",
        services=Service.query.filter_by(active=True, archived=False)
        .order_by(Service.display_order, Service.name)
        .all(),
        settings=settings(),
    )


@public_bp.get("/services/<slug>")
def service_detail(slug):
    service = Service.query.filter_by(
        slug=slug, active=True, archived=False
    ).first_or_404()
    works = (
        PortfolioItem.query.filter_by(
            service_id=service.id, published=True, archived=False
        )
        .order_by(PortfolioItem.display_order, PortfolioItem.created_at.desc())
        .all()
    )
    return render_template(
        "public/service_detail.html",
        service=service,
        works=works,
        settings=settings(),
    )


@public_bp.get("/our-work")
def portfolio_page():
    return render_template(
        "public/portfolio.html",
        works=PortfolioItem.query.filter_by(published=True, archived=False)
        .order_by(PortfolioItem.display_order, PortfolioItem.created_at.desc())
        .all(),
        settings=settings(),
    )


@public_bp.get("/media/<path:key>")
def media(key):
    try:
        return serve_local_image(key)
    except UploadError:
        abort(404)


@public_bp.route("/enquire", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def enquire():
    services = (
        Service.query.filter_by(active=True, archived=False)
        .order_by(Service.display_order)
        .all()
    )
    if request.method == "POST":
        # Honeypot: quietly accept bots without creating customer records.
        if request.form.get("website", "").strip():
            flash("Thank you. Your enquiry has been received.", "success")
            return redirect(url_for("public.enquire"))
        try:
            lead = create_lead(request.form, source="Web")
            flash(
                f"Thank you, {lead.full_name}. Your enquiry reference is {lead.reference}.",
                "success",
            )
            return redirect(url_for("public.enquire"))
        except DomainError as error:
            flash(str(error), "danger")
    return render_template(
        "public/enquire.html", services=services, settings=settings()
    )


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per 15 minutes", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = AdminUser.query.filter_by(email=email).first()
        if (
            user
            and user.active
            and check_password_hash(
                user.password_hash, request.form.get("password", "")
            )
        ):
            login_user(user, remember=False, fresh=True)
            return redirect(
                request.args.get("next")
                if (request.args.get("next") or "").startswith("/admin")
                else url_for("admin.dashboard")
            )
        flash("Email or password is incorrect.", "danger")
    return render_template("auth/login.html")


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))


@admin_bp.get("/")
@login_required
def dashboard():
    from .models import Payment

    metrics = {
        "total": Lead.query.count(),
        "open": Lead.query.filter_by(status="Open").count(),
        "won": Lead.query.filter_by(status="Closed Won").count(),
        "lost": Lead.query.filter_by(status="Closed Lost").count(),
        "projects": Project.query.filter(
            Project.status.in_(["Not Started", "In Progress", "On Hold"])
        ).count(),
        "paid": db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0))
        .filter_by(verified=True)
        .scalar(),
    }
    stages = {
        stage: Lead.query.filter_by(stage=stage).count()
        for stage in [
            "Prospecting",
            "Qualification",
            "Need Analysis",
            "Value Proposition",
            "Decision Makers",
            "Negotiation & Payment",
            "Closed Won",
        ]
    }
    return render_template(
        "admin/dashboard.html",
        metrics=metrics,
        stages=stages,
        leads=Lead.query.order_by(Lead.created_at.desc()).limit(8).all(),
    )


@admin_bp.get("/leads")
@login_required
def leads():
    query = Lead.query
    term = request.args.get("q", "").strip()
    if term:
        query = query.filter(
            or_(
                Lead.reference.ilike(f"%{term}%"),
                Lead.full_name.ilike(f"%{term}%"),
                Lead.phone.ilike(f"%{term}%"),
            )
        )
    for key, col in (
        ("stage", Lead.stage),
        ("status", Lead.status),
        ("source", Lead.source),
    ):
        if request.args.get(key):
            query = query.filter(col == request.args[key])
    page = query.order_by(Lead.created_at.desc()).paginate(
        page=max(1, request.args.get("page", 1, type=int)), per_page=20, error_out=False
    )
    return render_template("admin/leads.html", page=page)


@admin_bp.get("/leads/<int:lead_id>")
@login_required
def lead_detail(lead_id):
    lifecycle = [
        "Prospecting",
        "Qualification",
        "Need Analysis",
        "Value Proposition",
        "Decision Makers",
        "Negotiation & Payment",
        "Closed Won",
    ]
    lead = db.get_or_404(Lead, lead_id)
    current_index = lifecycle.index(lead.stage)
    edit_stage = request.args.get("edit_stage", type=int)
    selected_index = current_index
    if edit_stage is not None and 0 <= edit_stage <= current_index:
        selected_index = edit_stage
    return render_template(
        "admin/lead_detail.html",
        lead=lead,
        lifecycle=lifecycle,
        current_index=current_index,
        selected_index=selected_index,
    )


@admin_bp.post("/leads/<int:lead_id>/stage")
@login_required
def lead_stage(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    try:
        transition(lead, request.form.get("stage", ""), current_user)
        flash("Lead advanced.", "success")
    except DomainError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.lead_detail", lead_id=lead.id))


@admin_bp.post("/leads/<int:lead_id>/advance")
@login_required
def lead_advance(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    try:
        values = {
            key: value
            for key, value in request.form.items()
            if key in STAGE_DATA_FIELDS
        }
        target = request.form.get("stage", "")
        for field in ("challenges", "recommended_services", "verified_services"):
            if field in request.form:
                values[field] = [
                    value for value in request.form.getlist(field) if value.strip()
                ]
        quote_base = request.form.get("base_price")
        quote_discount = request.form.get("discount_amount", "0")
        quote_notes = request.form.get("notes", "")
        if values:
            update_stage_data(lead, values, current_user)
        if quote_base:
            save_quote(lead, quote_base, quote_discount, quote_notes, current_user)
        transition(lead, target, current_user)
        flash("Stage details saved and lead advanced.", "success")
    except DomainError as error:
        flash(str(error), "danger")
    return redirect(url_for("admin.lead_detail", lead_id=lead.id))


@admin_bp.post("/leads/<int:lead_id>/details")
@login_required
def lead_data(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    try:
        values = {
            key: value
            for key, value in request.form.items()
            if key in STAGE_DATA_FIELDS
        }
        for field in ("challenges", "recommended_services", "verified_services"):
            if field in request.form:
                values[field] = [
                    value for value in request.form.getlist(field) if value.strip()
                ]
        update_stage_data(lead, values, current_user, allow_closed=True)
        flash("Lead details saved.", "success")
    except DomainError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.lead_detail", lead_id=lead.id))


@admin_bp.post("/leads/<int:lead_id>/quote")
@login_required
def lead_quote(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    try:
        quote_fields = {
            "value_statement",
            "expected_benefits",
            "roi_statement",
            "recommended_services",
        }
        stage_values = {
            key: request.form.get(key, "")
            for key in quote_fields
            if key in request.form
        }
        if "recommended_services" in stage_values:
            stage_values["recommended_services"] = [
                item.strip()
                for item in stage_values["recommended_services"].split(",")
                if item.strip()
            ]
        if stage_values:
            update_stage_data(lead, stage_values, current_user)
        approve = request.form.get("approve") == "yes"
        revise = request.form.get("revise") == "yes"
        save_quote(
            lead,
            request.form.get("base_price"),
            request.form.get("discount_amount", "0"),
            request.form.get("notes", ""),
            current_user,
            approve,
            revise,
            request.form.get("approved_scope"),
        )
        flash(
            "Negotiated price saved and approved."
            if revise and approve
            else "Quote saved.",
            "success",
        )
    except DomainError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.lead_detail", lead_id=lead.id))


@admin_bp.post("/leads/<int:lead_id>/payments")
@login_required
def payment_add(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    try:
        record_payment(
            lead,
            request.form.get("amount"),
            request.form.get("method"),
            date.fromisoformat(request.form.get("received_on", "")),
            current_user,
            request.form.get("reference", ""),
            request.form.get("notes", ""),
        )
        flash("Payment recorded and awaiting verification.", "success")
    except (DomainError, ValueError) as e:
        flash(str(e) or "Enter a valid payment date.", "danger")
    return redirect(url_for("admin.lead_detail", lead_id=lead.id))


@admin_bp.post("/payments/<int:payment_id>/verify")
@login_required
def payment_verify(payment_id):
    from .models import Payment

    payment = db.get_or_404(Payment, payment_id)
    try:
        verify_payment(payment, current_user)
        flash("Payment verified.", "success")
    except DomainError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.lead_detail", lead_id=payment.lead_id))


@admin_bp.post("/leads/<int:lead_id>/closed-won")
@login_required
def lead_won(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    try:
        transition(lead, "Closed Won", current_user)
        flash("Lead closed Won and project created.", "success")
    except DomainError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.lead_detail", lead_id=lead.id))


@admin_bp.post("/leads/<int:lead_id>/closed-lost")
@login_required
def lead_lost(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    try:
        close_lost(
            lead,
            request.form.get("reason"),
            request.form.get("notes", ""),
            current_user,
        )
        flash("Lead closed Lost.", "success")
    except DomainError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.lead_detail", lead_id=lead.id))


@admin_bp.route("/services", methods=["GET", "POST"])
@login_required
def manage_services():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not name or Service.query.filter_by(slug=slug).first():
            flash("Enter a unique service name.", "danger")
        else:
            try:
                service = Service(
                    name=name[:120],
                    slug=slug,
                    short_description=request.form.get("short_description", "")[:300],
                    description=request.form.get("description", ""),
                    benefits=request.form.get("benefits", "")[:5000],
                    features=request.form.get("features", "")[:5000],
                    active="active" in request.form,
                    display_order=request.form.get("display_order", 0, type=int),
                )
                service.image_key = store_image(request.files.get("image"))
                db.session.add(service)
                db.session.commit()
                flash("Service added.", "success")
            except UploadError as error:
                flash(str(error), "danger")
        return redirect(url_for("admin.manage_services"))
    return render_template(
        "admin/services.html",
        services=Service.query.filter_by(archived=False)
        .order_by(Service.display_order)
        .all(),
    )


@admin_bp.post("/services/<int:service_id>")
@login_required
def edit_service(service_id):
    service = db.get_or_404(Service, service_id)
    service.name = request.form.get("name", service.name).strip()[:120]
    service.short_description = request.form.get("short_description", "")[:300]
    service.description = request.form.get("description", "")[:10000]
    service.benefits = request.form.get("benefits", "")[:5000]
    service.features = request.form.get("features", "")[:5000]
    service.active = "active" in request.form
    service.display_order = request.form.get("display_order", 0, type=int)
    try:
        service.image_key = store_image(request.files.get("image")) or service.image_key
        db.session.commit()
        flash("Service saved.", "success")
    except UploadError as error:
        db.session.rollback()
        flash(str(error), "danger")
    return redirect(url_for("admin.manage_services"))


@admin_bp.post("/services/<int:service_id>/archive")
@login_required
def archive_service(service_id):
    service = db.get_or_404(Service, service_id)
    service.archived = True
    service.active = False
    db.session.commit()
    flash("Service archived; historical leads are retained.", "success")
    return redirect(url_for("admin.manage_services"))


@admin_bp.route("/portfolio", methods=["GET", "POST"])
@login_required
def manage_portfolio():
    if request.method == "POST":
        entry = PortfolioItem(
            title=request.form.get("title", "").strip()[:180],
            description=request.form.get("description", "")[:10000],
            service_id=request.form.get("service_id", type=int) or None,
            location=request.form.get("location", "")[:180] or None,
            published="published" in request.form,
            display_order=request.form.get("display_order", 0, type=int),
        )
        if not entry.title:
            flash("Title is required.", "danger")
        else:
            try:
                if len(request.files.getlist("gallery")) > 10:
                    raise UploadError("Upload no more than 10 gallery images at once.")
                entry.image_key = store_image(request.files.get("image"))
                entry.gallery = [
                    key
                    for upload in request.files.getlist("gallery")
                    if (key := store_image(upload))
                ]
                db.session.add(entry)
                db.session.commit()
                flash("Portfolio item added.", "success")
            except UploadError as error:
                db.session.rollback()
                flash(str(error), "danger")
        return redirect(url_for("admin.manage_portfolio"))
    return render_template(
        "admin/portfolio.html",
        items=PortfolioItem.query.filter_by(archived=False)
        .order_by(PortfolioItem.display_order)
        .all(),
        services=Service.query.filter_by(archived=False).all(),
    )


@admin_bp.post("/portfolio/<int:item_id>")
@login_required
def edit_portfolio(item_id):
    item = db.get_or_404(PortfolioItem, item_id)
    item.title = request.form.get("title", item.title).strip()[:180]
    item.description = request.form.get("description", "")[:10000]
    item.location = request.form.get("location", "")[:180] or None
    item.service_id = request.form.get("service_id", type=int) or None
    item.published = "published" in request.form
    item.display_order = request.form.get("display_order", 0, type=int)
    try:
        if len(request.files.getlist("gallery")) > 10:
            raise UploadError("Upload no more than 10 gallery images at once.")
        item.image_key = store_image(request.files.get("image")) or item.image_key
        extra_images = [
            key
            for upload in request.files.getlist("gallery")
            if (key := store_image(upload))
        ]
        item.gallery = (item.gallery or []) + extra_images
        db.session.commit()
        flash("Portfolio item saved.", "success")
    except UploadError as error:
        db.session.rollback()
        flash(str(error), "danger")
    return redirect(url_for("admin.manage_portfolio"))


@admin_bp.post("/portfolio/<int:item_id>/archive")
@login_required
def archive_portfolio(item_id):
    item = db.get_or_404(PortfolioItem, item_id)
    item.archived = True
    item.published = False
    db.session.commit()
    flash("Portfolio item archived.", "success")
    return redirect(url_for("admin.manage_portfolio"))


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
def manage_settings():
    obj = settings()
    if request.method == "POST":
        for key in (
            "company_name",
            "introduction",
            "mission",
            "vision",
            "phone",
            "email",
            "address",
        ):
            setattr(obj, key, request.form.get(key, "").strip()[:5000])
        db.session.commit()
        flash("Company settings saved.", "success")
    return render_template("admin/settings.html", settings=obj)


@admin_bp.get("/projects")
@login_required
def projects():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template(
        "admin/projects.html",
        projects=projects,
    )


@admin_bp.get("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    project = db.get_or_404(Project, project_id)
    payments = project.lead.payments
    payment_totals = {
        "recorded": sum(
            (Decimal(str(payment.amount)) for payment in payments), Decimal("0.00")
        ),
        "verified": sum(
            (Decimal(str(payment.amount)) for payment in payments if payment.verified),
            Decimal("0.00"),
        ),
    }
    return render_template(
        "admin/project_detail.html",
        project=project,
        payment_totals=payment_totals,
        today=date.today().isoformat(),
    )


@admin_bp.post("/projects/<int:project_id>")
@login_required
def project_update(project_id):
    project = db.get_or_404(Project, project_id)
    status = request.form.get("status")
    if status not in PROJECT_STATUSES:
        flash("Choose a valid project status.", "danger")
    else:
        project.status = status
        project.internal_notes = request.form.get("internal_notes", "")[:5000]
        from .models import LeadActivity

        db.session.add(
            LeadActivity(
                lead_id=project.lead_id,
                actor_id=current_user.id,
                action="Project updated",
                details={"status": status},
            )
        )
        db.session.commit()
        flash("Project updated.", "success")
    return redirect(url_for("admin.project_detail", project_id=project.id))


@admin_bp.post("/projects/<int:project_id>/payments")
@login_required
def project_payment_add(project_id):
    project = db.get_or_404(Project, project_id)
    try:
        from .services import record_payment

        record_payment(
            project.lead,
            request.form.get("amount"),
            request.form.get("method"),
            date.fromisoformat(request.form.get("received_on", "")),
            current_user,
            request.form.get("reference", ""),
            request.form.get("notes", ""),
        )
        flash("Payment recorded and awaiting verification.", "success")
    except (DomainError, ValueError) as error:
        flash(str(error) or "Enter a valid payment date.", "danger")
    return redirect(url_for("admin.project_detail", project_id=project.id))


@admin_bp.post("/projects/<int:project_id>/payments/<int:payment_id>/verify")
@login_required
def project_payment_verify(project_id, payment_id):
    project = db.get_or_404(Project, project_id)
    from .models import Payment

    payment = db.get_or_404(Payment, payment_id)
    if payment.lead_id != project.lead_id:
        abort(404)
    try:
        verify_payment(payment, current_user)
        flash("Payment verified.", "success")
    except DomainError as error:
        flash(str(error), "danger")
    return redirect(url_for("admin.project_detail", project_id=project.id))


@admin_bp.post("/projects/<int:project_id>/updates")
@login_required
def project_add_progress(project_id):
    project = db.get_or_404(Project, project_id)
    title = request.form.get("title", "").strip()
    notes = request.form.get("notes", "").strip()
    uploads = [
        upload
        for upload in request.files.getlist("images")
        if upload and upload.filename
    ]
    if not title or len(title) > 180:
        flash("Add a progress update title (up to 180 characters).", "danger")
        return redirect(url_for("admin.project_detail", project_id=project.id))
    if len(notes) > 5000:
        flash("Progress notes must be 5,000 characters or fewer.", "danger")
        return redirect(url_for("admin.project_detail", project_id=project.id))
    if len(uploads) > 4:
        flash("Attach no more than four progress photos at once.", "danger")
        return redirect(url_for("admin.project_detail", project_id=project.id))
    try:
        image_urls = [store_image(upload) for upload in uploads]
        update = ProjectUpdate(
            project=project,
            created_by_id=current_user.id,
            title=title,
            notes=notes or None,
            images=image_urls,
        )
        db.session.add(update)
        db.session.add(
            LeadActivity(
                lead_id=project.lead_id,
                actor_id=current_user.id,
                action="Project progress updated",
                details={"title": title, "image_count": len(image_urls)},
            )
        )
        db.session.commit()
        flash("Project progress update added.", "success")
    except UploadError as error:
        db.session.rollback()
        flash(str(error), "danger")
    return redirect(url_for("admin.project_detail", project_id=project.id))


def api_error(message, status=400):
    return jsonify(
        error={
            "code": "validation_error" if status == 400 else "request_error",
            "message": message,
        }
    ), status


@api_bp.get("/openapi.json")
def openapi():
    return jsonify(
        {
            "openapi": "3.1.0",
            "info": {"title": "FARM360 API", "version": "1.0.0"},
            "servers": [{"url": "/api/v1"}],
            "paths": {
                "/services": {"get": {"summary": "List active services"}},
                "/portfolio": {"get": {"summary": "List published work"}},
                "/enquiries": {"post": {"summary": "Submit an enquiry"}},
                "/admin/leads": {
                    "get": {
                        "summary": "List leads",
                        "security": [{"sessionCookie": []}],
                    }
                },
                "/admin/leads/{id}/transition": {
                    "post": {
                        "summary": "Advance lead stage",
                        "security": [{"sessionCookie": []}],
                    }
                },
                "/admin/leads/{id}/payments": {
                    "post": {
                        "summary": "Record payment",
                        "security": [{"sessionCookie": []}],
                    }
                },
                "/admin/leads/{id}/closed-won": {
                    "post": {
                        "summary": "Close lead Won and create project",
                        "security": [{"sessionCookie": []}],
                    }
                },
                "/admin/projects": {
                    "get": {
                        "summary": "List projects",
                        "security": [{"sessionCookie": []}],
                    }
                },
            },
            "components": {
                "securitySchemes": {
                    "sessionCookie": {
                        "type": "apiKey",
                        "in": "cookie",
                        "name": "session",
                    }
                }
            },
        }
    )


@api_bp.get("/services")
def api_services():
    return jsonify(
        data=[
            {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "short_description": s.short_description,
                "description": s.description,
            }
            for s in Service.query.filter_by(active=True, archived=False)
            .order_by(Service.display_order)
            .all()
        ]
    )


@api_bp.get("/portfolio")
def api_portfolio():
    return jsonify(
        data=[
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "service": p.service.name if p.service else None,
                "location": p.location,
                "image": p.image_key,
                "completed_on": p.completed_on.isoformat() if p.completed_on else None,
            }
            for p in PortfolioItem.query.filter_by(published=True, archived=False)
            .order_by(PortfolioItem.display_order)
            .all()
        ]
    )


@api_bp.post("/enquiries")
@csrf.exempt
@limiter.limit("5 per hour")
def api_enquiries():
    try:
        lead = create_lead(request.get_json(silent=True) or {}, source="Web")
        return jsonify(data={"reference": lead.reference, "status": lead.status}), 201
    except DomainError as e:
        return api_error(str(e))


def api_admin(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify(
                error={
                    "code": "authentication_required",
                    "message": "Administrator sign-in is required.",
                }
            ), 401
        return fn(*args, **kwargs)

    return wrapped


@api_bp.get("/admin/leads")
@api_admin
def api_leads():
    page = Lead.query.order_by(Lead.created_at.desc()).paginate(
        page=max(1, request.args.get("page", 1, type=int)),
        per_page=min(100, max(1, request.args.get("per_page", 20, type=int))),
        error_out=False,
    )
    return jsonify(
        data=[
            {
                "id": lead.id,
                "reference": lead.reference,
                "full_name": lead.full_name,
                "phone": lead.phone,
                "service": lead.service_name_snapshot,
                "stage": lead.stage,
                "status": lead.status,
            }
            for lead in page.items
        ],
        pagination={
            "page": page.page,
            "per_page": page.per_page,
            "total": page.total,
            "pages": page.pages,
        },
    )


@api_bp.get("/admin/leads/<int:lead_id>")
@api_admin
def api_lead(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    return jsonify(
        data={
            "id": lead.id,
            "reference": lead.reference,
            "full_name": lead.full_name,
            "phone": lead.phone,
            "email": lead.email,
            "location": lead.location,
            "service": lead.service_name_snapshot,
            "description": lead.description,
            "stage": lead.stage,
            "status": lead.status,
            "stage_data": lead.stage_data,
            "quote": {
                "base": str(lead.quoted_price),
                "discount": str(lead.discount_amount),
                "final": str(lead.final_price),
                "approved": lead.quote_approved,
            },
            "payments": [
                {
                    "id": p.id,
                    "amount": str(p.amount),
                    "method": p.method,
                    "verified": p.verified,
                }
                for p in lead.payments
            ],
        }
    )


@api_bp.post("/admin/leads/<int:lead_id>/transition")
@api_admin
def api_transition(lead_id):
    try:
        lead = transition(
            db.get_or_404(Lead, lead_id),
            (request.get_json() or {}).get("stage"),
            current_user,
        )
        return jsonify(data={"stage": lead.stage, "status": lead.status})
    except DomainError as e:
        return api_error(str(e))


@api_bp.patch("/admin/leads/<int:lead_id>/details")
@api_admin
def api_details(lead_id):
    try:
        update_stage_data(
            db.get_or_404(Lead, lead_id), request.get_json() or {}, current_user
        )
        return jsonify(data={"saved": True})
    except DomainError as e:
        return api_error(str(e))


@api_bp.post("/admin/leads/<int:lead_id>/quote")
@api_admin
def api_quote(lead_id):
    d = request.get_json() or {}
    try:
        lead = save_quote(
            db.get_or_404(Lead, lead_id),
            d.get("base_price"),
            d.get("discount_amount", 0),
            d.get("notes", ""),
            current_user,
            bool(d.get("approve")),
            bool(d.get("revise")),
            d.get("approved_scope"),
        )
        return jsonify(
            data={"final_price": str(lead.final_price), "approved": lead.quote_approved}
        )
    except DomainError as e:
        return api_error(str(e))


@api_bp.post("/admin/leads/<int:lead_id>/payments")
@api_admin
def api_payment(lead_id):
    d = request.get_json() or {}
    try:
        p = record_payment(
            db.get_or_404(Lead, lead_id),
            d.get("amount"),
            d.get("method"),
            date.fromisoformat(d.get("received_on", "")),
            current_user,
            d.get("reference", ""),
            d.get("notes", ""),
        )
        return jsonify(data={"id": p.id, "verified": False}), 201
    except (DomainError, ValueError) as e:
        return api_error(str(e) or "Invalid payment date")


@api_bp.post("/admin/payments/<int:payment_id>/verify")
@api_admin
def api_verify_payment(payment_id):
    from .models import Payment

    try:
        p = verify_payment(db.get_or_404(Payment, payment_id), current_user)
        return jsonify(data={"id": p.id, "verified": p.verified})
    except DomainError as e:
        return api_error(str(e))


@api_bp.post("/admin/leads/<int:lead_id>/closed-won")
@api_admin
def api_won(lead_id):
    try:
        p = transition(db.get_or_404(Lead, lead_id), "Closed Won", current_user)
        return jsonify(data={"project_reference": p.reference}), 201
    except DomainError as e:
        return api_error(str(e))


@api_bp.post("/admin/leads/<int:lead_id>/closed-lost")
@api_admin
def api_lost(lead_id):
    d = request.get_json() or {}
    try:
        lead = close_lost(
            db.get_or_404(Lead, lead_id),
            d.get("reason"),
            d.get("notes", ""),
            current_user,
        )
        return jsonify(data={"status": lead.status})
    except DomainError as e:
        return api_error(str(e))


@api_bp.get("/admin/projects")
@api_admin
def api_projects():
    return jsonify(
        data=[
            {
                "id": p.id,
                "reference": p.reference,
                "lead_id": p.lead_id,
                "client_name": p.client_name,
                "status": p.status,
                "final_value": str(p.final_value),
            }
            for p in Project.query.order_by(Project.created_at.desc()).all()
        ]
    )


@api_bp.patch("/admin/projects/<int:project_id>")
@api_admin
def api_project_update(project_id):
    project = db.get_or_404(Project, project_id)
    d = request.get_json() or {}
    status = d.get("status", project.status)
    if status not in PROJECT_STATUSES:
        return api_error("Choose a valid project status.")
    project.status = status
    if "internal_notes" in d:
        project.internal_notes = str(d["internal_notes"])[:5000]
    from .models import LeadActivity

    db.session.add(
        LeadActivity(
            lead_id=project.lead_id,
            actor_id=current_user.id,
            action="Project updated",
            details={"status": status},
        )
    )
    db.session.commit()
    return jsonify(data={"id": project.id, "status": project.status})


@api_bp.post("/admin/services")
@api_admin
def api_create_service():
    d = request.get_json() or {}
    name = str(d.get("name", "")).strip()[:120]
    slug = re.sub(r"[^a-z0-9]+", "-", str(d.get("slug") or name).lower()).strip("-")
    if not name or not slug:
        return api_error("Service name is required.")
    if Service.query.filter_by(slug=slug).first():
        return api_error("Service slug already exists.", 409)
    service = Service(
        name=name,
        slug=slug,
        short_description=str(d.get("short_description", ""))[:300],
        description=str(d.get("description", ""))[:10000],
        active=bool(d.get("active", True)),
        display_order=int(d.get("display_order", 0)),
    )
    db.session.add(service)
    db.session.commit()
    return jsonify(data={"id": service.id, "slug": service.slug}), 201


@api_bp.patch("/admin/services/<int:service_id>")
@api_admin
def api_update_service(service_id):
    service = db.get_or_404(Service, service_id)
    d = request.get_json() or {}
    for key, limit in (
        ("name", 120),
        ("short_description", 300),
        ("description", 10000),
    ):
        if key in d:
            setattr(service, key, str(d[key])[:limit])
    if "active" in d:
        service.active = bool(d["active"])
    if "display_order" in d:
        try:
            service.display_order = int(d["display_order"])
        except (ValueError, TypeError):
            return api_error("Display order must be an integer.")
    db.session.commit()
    return jsonify(data={"id": service.id, "active": service.active})


@api_bp.delete("/admin/services/<int:service_id>")
@api_admin
def api_archive_service(service_id):
    service = db.get_or_404(Service, service_id)
    service.active = False
    service.archived = True
    db.session.commit()
    return jsonify(data={"id": service.id, "archived": True})


@api_bp.post("/admin/portfolio")
@api_admin
def api_create_portfolio():
    d = request.get_json() or {}
    title = str(d.get("title", "")).strip()[:180]
    if not title:
        return api_error("Portfolio title is required.")
    item = PortfolioItem(
        title=title,
        description=str(d.get("description", ""))[:10000],
        service_id=d.get("service_id"),
        location=str(d.get("location", ""))[:180] or None,
        published=bool(d.get("published", False)),
        display_order=int(d.get("display_order", 0)),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(data={"id": item.id}), 201


@api_bp.patch("/admin/portfolio/<int:item_id>")
@api_admin
def api_update_portfolio(item_id):
    item = db.get_or_404(PortfolioItem, item_id)
    d = request.get_json() or {}
    for key, limit in (("title", 180), ("description", 10000), ("location", 180)):
        if key in d:
            setattr(item, key, str(d[key])[:limit] or None)
    if "published" in d:
        item.published = bool(d["published"])
    if "service_id" in d:
        item.service_id = d["service_id"] or None
    if "display_order" in d:
        try:
            item.display_order = int(d["display_order"])
        except (ValueError, TypeError):
            return api_error("Display order must be an integer.")
    db.session.commit()
    return jsonify(data={"id": item.id, "published": item.published})


@api_bp.delete("/admin/portfolio/<int:item_id>")
@api_admin
def api_archive_portfolio(item_id):
    item = db.get_or_404(PortfolioItem, item_id)
    item.archived = True
    item.published = False
    db.session.commit()
    return jsonify(data={"id": item.id, "archived": True})
