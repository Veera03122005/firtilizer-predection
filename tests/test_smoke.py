import pytest
from models import Prediction, User
from extensions import db


def test_public_routes(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Smart Fertilizer Advisor" in r.data

    r = client.get("/about")
    assert r.status_code == 200
    assert b"Model Card" in r.data

    r = client.get("/contact")
    assert r.status_code == 200

    r = client.get("/health")
    assert r.status_code == 200
    json_data = r.get_json()
    assert json_data["model_loaded"] is True
    assert json_data["db"] == "ok"


def test_auth_protection(client):
    for path in ["/dashboard", "/predictor", "/history"]:
        r = client.get(path)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]


def test_authenticated_pages(auth_client):
    for path in ["/dashboard", "/predictor", "/history"]:
        r = auth_client.get(path)
        assert r.status_code == 200


def test_predict_and_result_flow(app, auth_client):
    # Predict Wheat
    resp = auth_client.post(
        "/predict",
        data={
            "location": "Ludhiana",
            "temperature": "28",
            "humidity": "60",
            "moisture": "45",
            "soil": "Loamy",
            "crop": "Wheat",
            "nitrogen": "12",
            "phosphorous": "36",
            "potassium": "0",
            "area_value": "2.0",
            "area_unit": "acre",
            "rating_n": "Medium",
            "rating_p": "Medium",
            "rating_k": "Medium",
        },
    )
    assert resp.status_code == 302
    assert "/result/" in resp.headers["Location"]

    # Follow redirect to result page
    result_url = resp.headers["Location"]
    r2 = auth_client.get(result_url)
    assert r2.status_code == 200
    assert b"Nutrient Recommendation" in r2.data
    assert b"DAP" in r2.data


def test_ownership_isolation(app, auth_client, client):
    with app.app_context():
        user2 = User(
            name="Other Farmer",
            email="other@example.com",
            password_hash="fakehash",
            preferred_language="en",
        )
        db.session.add(user2)
        db.session.commit()

        pred_other = Prediction(
            user_id=user2.id,
            temperature=30,
            humidity=60,
            moisture=40,
            soil_type="Sandy",
            crop_type="Wheat",
            nitrogen=40,
            phosphorous=20,
            potassium=10,
            fertilizer="Urea",
            confidence=0.9,
            model_version="test",
        )
        db.session.add(pred_other)
        db.session.commit()
        other_pred_id = pred_other.id

    # auth_client is logged in as test@example.com (user 1), attempting to view other_pred_id must 404
    r = auth_client.get(f"/result/{other_pred_id}")
    assert r.status_code == 404


def test_contact_submission(client, app):
    r = client.post(
        "/contact",
        data={
            "name": "Suresh",
            "email": "suresh@example.com",
            "message": "When is the best time to apply DAP on wheat?",
        },
    )
    assert r.status_code == 302
    assert r.headers["Location"] == "/contact"

