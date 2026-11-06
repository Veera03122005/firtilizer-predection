import pytest
from services.ml_service import ml_service
from services.dosage_service import compute_dosage


def test_paddy_predicts():
    assert ml_service.model_loaded is True
    res = ml_service.predict({
        "temperature": 32.0,
        "humidity": 65.0,
        "moisture": 50.0,
        "soil": "Clayey",
        "crop": "Paddy",
        "nitrogen": 35,
        "potassium": 0,
        "phosphorous": 0,
    })
    assert res["fertilizer"] == "Urea"
    assert res["confidence"] > 0.5
    assert len(res["top3"]) == 3
    assert res["top3"][0]["label"] == "Urea"


def test_unknown_crop_rejected():
    with pytest.raises(ValueError, match="Unknown crop type 'Rice'"):
        ml_service.predict({
            "temperature": 30.0,
            "humidity": 60.0,
            "moisture": 45.0,
            "soil": "Loamy",
            "crop": "Rice",
            "nitrogen": 30,
            "potassium": 10,
            "phosphorous": 20,
        })


def test_ood_detection():
    # Nitrogen 150 is out of training range (max 42)
    res = ml_service.predict({
        "temperature": 30.0,
        "humidity": 60.0,
        "moisture": 45.0,
        "soil": "Loamy",
        "crop": "Wheat",
        "nitrogen": 150,
        "potassium": 10,
        "phosphorous": 20,
    })
    assert "Nitrogen" in res["ood_fields"]


def test_options_contains_paddy_not_rice():
    opts = ml_service.options()
    assert "Paddy" in opts["crop_types"]
    assert "Rice" not in opts["crop_types"]
    assert len(opts["crop_types"]) == 11
    assert len(opts["soil_types"]) == 5


def test_dosage_worked_example():
    """Matches AGENTS.md rule 40 & FEATURE-DEVELOPMENT 10.3 invariant:
    Wheat, 2 acres, Medium ratings -> DAP 105.6 kg, MOP 54.0 kg, Urea 169.8 kg, total 5702.
    """
    res = compute_dosage(
        crop="Wheat",
        fertilizer="DAP",
        area_value=2.0,
        area_unit="acre",
        ratings={"N": "Medium", "P": "Medium", "K": "Medium"},
    )
    by_prod = {line["product"]: line for line in res["lines"]}
    assert abs(by_prod["DAP"]["kg_total"] - 105.6) < 0.2
    assert abs(by_prod["MOP"]["kg_total"] - 54.0) < 0.2
    assert abs(by_prod["Urea"]["kg_total"] - 169.8) < 0.2
    assert abs(res["total_cost"] - 5702) <= 2

