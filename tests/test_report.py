import pytest
from models import Prediction
from services.dosage_service import compute_dosage
import json
from extensions import db


def test_pdf_report_download(auth_client, app):
    with app.app_context():
        dosage = compute_dosage("Wheat", "DAP", 2.0, "acre")
        pred = Prediction(
            user_id=1,
            location="Ludhiana",
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
        db.session.add(pred)
        db.session.commit()
        pred_id = pred.id

    res = auth_client.get(f"/report/{pred_id}.pdf")
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "application/pdf"
    assert res.data.startswith(b"%PDF")
