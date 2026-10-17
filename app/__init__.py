import os
from flask import Flask, jsonify, render_template, request
from sqlalchemy import text
from config import Config, ProductionConfig
from .extensions import csrf, db, limiter, login_manager, migrate


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    debug_mode = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.config.from_object(Config if debug_mode else ProductionConfig)
    if test_config:
        app.config.update(test_config)
    if not app.testing and (
        not app.config.get("SECRET_KEY")
        or app.config["SECRET_KEY"] == "dev-only-change-me"
    ):
        if not debug_mode:
            raise RuntimeError("Set a strong SECRET_KEY before production startup")
    if (
        not app.testing
        and app.config.get("UPLOAD_STORAGE_BACKEND") == "local"
        and os.getenv("FLASK_DEBUG", "0") != "1"
    ):
        app.logger.warning(
            "Local uploads are disabled in production; configure Cloudinary before enabling image uploads"
        )
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"
    csrf.init_app(app)
    limiter.init_app(app)
    from . import models  # noqa: F401
    from .routes import admin_bp, api_bp, auth_bp, public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    @app.get("/healthz")
    def healthz():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(status="ok", database="ok")
        except Exception:
            db.session.rollback()
            return jsonify(status="error", database="unavailable"), 503

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify(
                error={"code": "not_found", "message": "Resource not found"}
            ), 404
        return render_template("errors/404.html"), 404

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self' https://cdn.jsdelivr.net; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; script-src 'self' https://cdn.jsdelivr.net",
        )
        if not app.testing and app.config["SESSION_COOKIE_SECURE"]:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    register_cli(app)
    return app


def register_cli(app):
    import click
    from werkzeug.security import generate_password_hash
    from .models import AdminUser, Service

    @app.cli.command("seed-services")
    def seed_services():
        defaults = [
            (
                "Terrace Gardening",
                "terrace-gardening",
                "Thoughtful garden design and installation for terraces and rooftops.",
                "Plan and develop productive, welcoming terrace gardens with optional ongoing care.",
                "Make better use of balconies, terraces and rooftops.\nChoose planting suited to the available light and space.\nCreate a welcoming place to grow and unwind.",
                "Space and sunlight review\nPlanting and layout plan\nInstallation and care options",
            ),
            (
                "Home Gardening",
                "home-gardening",
                "Gardens for front yards, backyards, herbs, vegetables, and fruit.",
                "Create a home growing space suited to your available area, goals, and local conditions.",
                "Bring food and greenery into everyday spaces.\nPlan around your household’s goals and available time.\nMake use of existing soil, containers or beds.",
                "Garden and site discussion\nLayout and plant selection\nSetup and maintenance options",
            ),
            (
                "Farm Management",
                "farm-management",
                "Agricultural land management for owners who need hands-on support.",
                "Coordinate land preparation, crop planning, cultivation, maintenance, and harvest as an agricultural service.",
                "Coordinate practical work across the growing cycle.\nPlan around land, water and crop conditions.\nKeep key activities and next steps organized.",
                "Land and resource review\nCrop and activity planning\nCultivation and maintenance coordination",
            ),
            (
                "Farm Rental",
                "farm-rental",
                "Discuss leasing agricultural land for independent cultivation.",
                "A rental arrangement where FARM360 leases land and cultivates crops under agreed terms, distinct from fee-based farm management.",
                "Explore an agreed land-use arrangement.\nDiscuss responsibilities and terms before cultivation.\nMatch the growing plan to the available land.",
                "Land and suitability discussion\nRental terms and responsibilities\nCultivation plan under agreed terms",
            ),
        ]
        for order, (name, slug, short, detail, benefits, features) in enumerate(
            defaults, 1
        ):
            service = Service.query.filter_by(slug=slug).first()
            if not service:
                db.session.add(
                    Service(
                        name=name,
                        slug=slug,
                        short_description=short,
                        description=detail,
                        benefits=benefits,
                        features=features,
                        display_order=order,
                        active=True,
                    )
                )
            else:
                if not service.benefits:
                    service.benefits = benefits
                if not service.features:
                    service.features = features
        db.session.commit()
        click.echo("Default services are present.")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(email, password):
        email = email.strip().lower()
        if len(password) < 12:
            raise click.ClickException("Password must be at least 12 characters.")
        if AdminUser.query.filter_by(email=email).first():
            raise click.ClickException(
                "An administrator with this email already exists."
            )
        db.session.add(
            AdminUser(email=email, password_hash=generate_password_hash(password))
        )
        db.session.commit()
        click.echo("Administrator created.")
