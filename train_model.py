"""Rebuild the missing fertilizer_model.pkl in the exact shape app.py expects:
{"model": <sklearn classifier>, "label_encoders": {"Soil Type", "Crop Type", "Fertilizer Name"}}
Feature order (from app.py line 73): temp, humidity, moisture, soil_enc, crop_enc, N, K, P
"""
import pickle, sys
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score

csv, out = sys.argv[1], sys.argv[2]
df = pd.read_csv(csv)
df.columns = df.columns.str.strip()          # dataset has "Humidity " with a trailing space
print("rows", len(df))
print("soil:", sorted(df["Soil Type"].unique()))
print("crop:", sorted(df["Crop Type"].unique()))
print("fert counts:", df["Fertilizer Name"].value_counts().to_dict())
for c in ["Temparature", "Humidity", "Moisture", "Nitrogen", "Potassium", "Phosphorous"]:
    print(f"range {c}: {df[c].min()}-{df[c].max()}")

encs = {c: LabelEncoder().fit(df[c]) for c in ["Soil Type", "Crop Type", "Fertilizer Name"]}
X = np.column_stack([
    df["Temparature"], df["Humidity"], df["Moisture"],
    encs["Soil Type"].transform(df["Soil Type"]), encs["Crop Type"].transform(df["Crop Type"]),
    df["Nitrogen"], df["Potassium"], df["Phosphorous"],
])
y = encs["Fertilizer Name"].transform(df["Fertilizer Name"])

cv = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)  # smallest class (10-26-26) has 7 rows
models = {
    "RandomForest": RandomForestClassifier(n_estimators=200, random_state=42),
    "DecisionTree": DecisionTreeClassifier(random_state=42),
    "LogisticRegression": LogisticRegression(max_iter=5000),
}
for name, m in models.items():
    s = cross_val_score(m, X, y, cv=cv)
    print(f"cv {name}: mean={s.mean():.3f} min={s.min():.3f}")

# NPK-only and env-only, to show where the signal is
for label, cols in [("NPK only", [5, 6, 7]), ("env+soil+crop only", [0, 1, 2, 3, 4])]:
    s = cross_val_score(RandomForestClassifier(n_estimators=200, random_state=42), X[:, cols], y, cv=cv)
    print(f"cv RF {label}: mean={s.mean():.3f}")

rf = RandomForestClassifier(n_estimators=200, random_state=42).fit(X, y)
names = ["Temp", "Humidity", "Moisture", "Soil", "Crop", "N", "K", "P"]
print("importances:", {n: round(v, 3) for n, v in sorted(zip(names, rf.feature_importances_), key=lambda t: -t[1])})

with open(out, "wb") as f:
    pickle.dump({"model": rf, "label_encoders": encs}, f)
print("saved", out)

