import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from werkzeug.security import generate_password_hash
from app_factory import create_app
from config import TestConfig
from extensions import db
from models import User


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash=generate_password_hash("TestPassword@123"),
            preferred_language="en",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    res = client.post("/login", data={"email": "test@example.com", "password": "TestPassword@123"})
    assert res.status_code == 302
    return client
