import pytest
from models import Prediction


def test_api_chat_flow(auth_client, app):
    # Create prediction
    with app.app_context():
        pred = Prediction.query.filter_by(crop_type="Wheat").first()
        if not pred:
            from services.dosage_service import compute_dosage
            import json
            dosage = compute_dosage("Wheat", "DAP", 2.0, "acre")
            pred = Prediction(
                user_id=1,
                temperature=28,
                humidity=60,
                moisture=45,
                soil_type="Loamy",
                crop_type="Wheat",
                nitrogen=12,
                phosphorous=36,
                potassium=0,
                fertilizer="DAP",
                confidence=0.92,
                dosage_json=json.dumps(dosage),
                total_cost=dosage.get("total_cost"),
                model_version="test",
            )
            from extensions import db
            db.session.add(pred)
            db.session.commit()
            pred_id = pred.id
        else:
            pred_id = pred.id

    # Post question
    res = auth_client.post(
        "/api/chat",
        json={"prediction_id": pred_id, "question": "Why should I apply DAP?", "language": "en"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "answer" in data
    assert len(data["sources"]) > 0

    # Get chat history for prediction
    res_history = auth_client.get(f"/api/chat/{pred_id}")
    assert res_history.status_code == 200
    hist = res_history.get_json()
    assert len(hist["messages"]) >= 2  # user + assistant


def test_api_weather(client):
    # Geocoding Guntur
    res = client.get("/api/weather?location=Guntur")
    # In sandbox or offline it could be 200 or 502 depending on network, handled gracefully
    assert res.status_code in (200, 502)
