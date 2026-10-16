import pytest
from app import create_app
from app.extensions import db
from app.models import AdminUser, Service
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
        db.session.add(
            Service(
                name="Garden",
                slug="garden",
                short_description="Garden care",
                description="Garden service",
                active=True,
            )
        )
        db.session.add(
            AdminUser(
                email="admin@example.com",
                password_hash=generate_password_hash("long-test-password"),
            )
        )
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    client.post(
        "/login", data={"email": "admin@example.com", "password": "long-test-password"}
    )
    return client
