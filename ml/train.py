import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "ml" / "data" / "Fertilizer Prediction.csv"
ARTIFACTS_DIR = BASE_DIR / "ml" / "artifacts"


def train_model(csv_path: Path = DATA_PATH, artifacts_dir: Path = ARTIFACTS_DIR):
    if not csv_path.exists():
        raise FileNotFoundError(f"Training dataset not found at {csv_path}")

    artifacts_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    if "Temparature" in df.columns:
        df = df.rename(columns={"Temparature": "Temperature"})

    num_cols = ["Temperature", "Humidity", "Moisture", "Nitrogen", "Potassium", "Phosphorous"]
    cat_cols = ["Soil Type", "Crop Type"]
    target_col = "Fertilizer Name"
    feature_cols = ["Temperature", "Humidity", "Moisture", "Soil Type", "Crop Type", "Nitrogen", "Potassium", "Phosphorous"]

    X = df[feature_cols]
    y = df[target_col]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", "passthrough", num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ]
    )

    clf = RandomForestClassifier(n_estimators=300, random_state=42)
    pipeline = Pipeline(steps=[("prep", preprocessor), ("clf", clf)])

    # 4-fold Stratified CV
    skf = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
    acc_scores = []
    f1_scores = []
    y_true_all = []
    y_pred_all = []

    for train_idx, val_idx in skf.split(X, y):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

        fold_pipeline = Pipeline(steps=[
            ("prep", ColumnTransformer(
                transformers=[
                    ("num", "passthrough", num_cols),
                    ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
                ]
            )),
            ("clf", RandomForestClassifier(n_estimators=300, random_state=42))
        ])
        fold_pipeline.fit(X_tr, y_tr)
        preds = fold_pipeline.predict(X_val)

        acc_scores.append(accuracy_score(y_val, preds))
        f1_scores.append(f1_score(y_val, preds, average="macro"))
        y_true_all.extend(y_val)
        y_pred_all.extend(preds)

    logger.info(f"CV Accuracy: {np.mean(acc_scores):.4f} +/- {np.std(acc_scores):.4f}")
    logger.info(f"CV Macro F1: {np.mean(f1_scores):.4f}")
    logger.info("Classification report:\n" + classification_report(y_true_all, y_pred_all))
    logger.info("Confusion matrix:\n" + str(confusion_matrix(y_true_all, y_pred_all)))

    # Fit on all rows
    pipeline.fit(X, y)

    # Feature importance mapping
    prep_step = pipeline.named_steps["prep"]
    cat_feature_names = list(prep_step.named_transformers_["cat"].get_feature_names_out(cat_cols))
    all_transformed_features = num_cols + cat_feature_names
    importances = pipeline.named_steps["clf"].feature_importances_

    # Aggregate importance by original feature
    feature_importance_dict = {}
    for orig in feature_cols:
        if orig in num_cols:
            idx = all_transformed_features.index(orig)
            feature_importance_dict[orig] = round(float(importances[idx]), 3)
        else:
            total_imp = sum(
                float(importances[i])
                for i, name in enumerate(all_transformed_features)
                if name.startswith(orig + "_")
            )
            feature_importance_dict[orig] = round(total_imp, 3)

    # Ranges
    ranges = {}
    for col in num_cols:
        ranges[col] = [int(df[col].min()), int(df[col].max())]

    classes = sorted(list(y.unique()))
    soil_types = sorted(list(df["Soil Type"].unique()))
    crop_types = sorted(list(df["Crop Type"].unique()))

    model_version = f"{datetime.now(timezone.utc).strftime('%Y.%m.%d')}-rf300"
    meta = {
        "model_version": model_version,
        "algorithm": "RandomForestClassifier(n_estimators=300)",
        "sklearn_version": sklearn.__version__,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(df),
        "features": feature_cols,
        "classes": classes,
        "soil_types": soil_types,
        "crop_types": crop_types,
        "ranges": ranges,
        "cv": {
            "folds": 4,
            "accuracy_mean": round(float(np.mean(acc_scores)), 4),
            "accuracy_std": round(float(np.std(acc_scores)), 4),
            "f1_macro": round(float(np.mean(f1_scores)), 4),
        },
        "feature_importance": feature_importance_dict,
    }

    joblib.dump(pipeline, artifacts_dir / "fertilizer_pipeline.joblib")
    with open(artifacts_dir / "model_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved artifacts to {artifacts_dir}")
    return meta


if __name__ == "__main__":
    train_model()

