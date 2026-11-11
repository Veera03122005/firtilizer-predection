import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple
import joblib
import numpy as np
import pandas as pd
import sklearn

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "ml" / "artifacts"
PIPELINE_PATH = ARTIFACTS_DIR / "fertilizer_pipeline.joblib"
META_PATH = ARTIFACTS_DIR / "model_meta.json"


class MLService:
    def __init__(self, artifacts_dir: Path = ARTIFACTS_DIR):
        self.artifacts_dir = artifacts_dir
        self.pipeline = None
        self.meta: Dict[str, Any] = {}
        self.model_loaded = False
        self.load_artifacts()

    def load_artifacts(self) -> bool:
        pipe_path = self.artifacts_dir / "fertilizer_pipeline.joblib"
        meta_path = self.artifacts_dir / "model_meta.json"

        if not pipe_path.exists() or not meta_path.exists():
            logger.info("ML artifacts not found. Training model automatically...")
            try:
                from ml.train import train_model
                train_model(artifacts_dir=self.artifacts_dir)
            except Exception as e:
                logger.error(f"Automatic ML model training failed: {e}")
                self.model_loaded = False
                return False

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                self.meta = json.load(f)

            self.pipeline = joblib.load(pipe_path)
            self.model_loaded = True

            meta_sk = self.meta.get("sklearn_version")
            if meta_sk and meta_sk != sklearn.__version__:
                logger.warning(
                    f"scikit-learn version mismatch: model trained with {meta_sk}, running with {sklearn.__version__}"
                )
            return True
        except Exception as e:
            logger.error(f"Failed to load ML artifacts: {e}")
            self.model_loaded = False
            return False

    def options(self) -> Dict[str, List[str]]:
        if not self.model_loaded or not self.meta:
            return {
                "soil_types": ["Black", "Clayey", "Loamy", "Red", "Sandy"],
                "crop_types": [
                    "Barley", "Cotton", "Ground Nuts", "Maize", "Millets",
                    "Oil seeds", "Paddy", "Pulses", "Sugarcane", "Tobacco", "Wheat"
                ],
            }
        return {
            "soil_types": self.meta.get("soil_types", []),
            "crop_types": self.meta.get("crop_types", []),
        }

    def check_ood(self, inputs: Dict[str, Any]) -> List[str]:
        if not self.model_loaded or "ranges" not in self.meta:
            return []
        ranges = self.meta["ranges"]
        mapping = {
            "Temperature": inputs.get("temperature"),
            "Humidity": inputs.get("humidity"),
            "Moisture": inputs.get("moisture"),
            "Nitrogen": inputs.get("nitrogen"),
            "Potassium": inputs.get("potassium"),
            "Phosphorous": inputs.get("phosphorous"),
        }
        ood = []
        for feature, val in mapping.items():
            if val is not None and feature in ranges:
                low, high = ranges[feature]
                try:
                    num_val = float(val)
                    if num_val < low or num_val > high:
                        ood.append(feature)
                except (ValueError, TypeError):
                    pass
        return ood

    def predict(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.model_loaded:
            raise RuntimeError("Model not trained — run python ml/train.py")

        soil = inputs.get("soil") or inputs.get("soil_type")
        crop = inputs.get("crop") or inputs.get("crop_type")

        valid_soils = self.meta.get("soil_types", [])
        valid_crops = self.meta.get("crop_types", [])

        if soil not in valid_soils:
            raise ValueError(f"Unknown soil type '{soil}'. Allowed: {valid_soils}")
        if crop not in valid_crops:
            raise ValueError(f"Unknown crop type '{crop}'. Allowed: {valid_crops}")

        temp = float(inputs["temperature"])
        humidity = float(inputs["humidity"])
        moisture = float(inputs["moisture"])
        nitrogen = int(inputs["nitrogen"])
        potassium = int(inputs["potassium"])
        phosphorous = int(inputs["phosphorous"])

        row_df = pd.DataFrame([{
            "Temperature": temp,
            "Humidity": humidity,
            "Moisture": moisture,
            "Soil Type": soil,
            "Crop Type": crop,
            "Nitrogen": nitrogen,
            "Potassium": potassium,
            "Phosphorous": phosphorous,
        }])

        probs = self.pipeline.predict_proba(row_df)[0]
        classes = self.pipeline.classes_

        top_idx = int(np.argmax(probs))
        top_fertilizer = str(classes[top_idx])
        top_conf = round(float(probs[top_idx]), 4)

        # Top 3 classes
        top3_indices = np.argsort(probs)[::-1][:3]
        top3 = [
            {"label": str(classes[i]), "p": round(float(probs[i]), 4)}
            for i in top3_indices
        ]

        ood_fields = self.check_ood({
            "temperature": temp,
            "humidity": humidity,
            "moisture": moisture,
            "nitrogen": nitrogen,
            "potassium": potassium,
            "phosphorous": phosphorous,
        })

        return {
            "fertilizer": top_fertilizer,
            "confidence": top_conf,
            "top3": top3,
            "ood_fields": ood_fields,
            "model_version": self.meta.get("model_version", "unknown"),
        }


# Singleton instance
ml_service = MLService()

