import pytest
from models import User
from extensions import db
from werkzeug.security import generate_password_hash


def test_register_and_login(client, app):
    # Register new user
    r = client.post(
        "/register",
        data={
            "name": "Ramesh Patel",
            "email": "ramesh@example.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
            "preferred_language": "te",
        },
    )
    assert r.status_code == 302
    assert r.headers["Location"] == "/dashboard"

    with app.app_context():
        u = User.query.filter_by(email="ramesh@example.com").first()
        assert u is not None
        assert u.name == "Ramesh Patel"
        assert u.preferred_language == "te"

    # Log out to test registration again
    client.post("/logout")

    # Duplicate registration rejected
    r_dup = client.post(
        "/register",
        data={
            "name": "Ramesh Duplicate",
            "email": "ramesh@example.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
            "preferred_language": "en",
        },
    )
    assert r_dup.status_code == 200
    assert b"already exists" in r_dup.data


def test_login_and_logout(client, app):
    with app.app_context():
        u = User(
            name="Login Tester",
            email="logintester@example.com",
            password_hash=generate_password_hash("Correct@Pass1"),
            preferred_language="en",
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()

    # Invalid login
    r_fail = client.post(
        "/login",
        data={"email": "logintester@example.com", "password": "WrongPassword"},
    )
    assert r_fail.status_code == 200
    assert b"Email or password is incorrect" in r_fail.data

    # Valid login
    r_ok = client.post(
        "/login",
        data={"email": "logintester@example.com", "password": "Correct@Pass1"},
    )
    assert r_ok.status_code == 302
    assert r_ok.headers["Location"] == "/dashboard"

    # Logout
    r_logout = client.post("/logout")
    assert r_logout.status_code == 302
    assert r_logout.headers["Location"] == "/"
