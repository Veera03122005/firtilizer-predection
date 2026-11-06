# 4. Database

Data storage for Smart Fertilizer Advisor: the SQLite schema (users, predictions, chats, contact messages), the file-based stores (model artifacts, vector index, JSON reference data), and how they are created, migrated and backed up.

---

## 4.1 Storage overview

| Store | Technology | Location | Created by | In git? |
| --- | --- | --- | --- | --- |
| Application DB | SQLite (Flask-SQLAlchemy) | `instance/app.db` | `flask --app app init-db` | No |
| ML artifacts | joblib + JSON | `ml/artifacts/` | `python ml/train.py` | No |
| Vector index | FAISS + JSON | `rag/index/` | `python rag/build_index.py` | No |
| Reference data | JSON | `data/crop_requirements.json`, `data/fertilizer_products.json` | Hand-edited | Yes |
| Knowledge base | Markdown | `knowledge_base/` | Hand-written, reviewed | Yes |
| Training data | CSV | `ml/data/Fertilizer Prediction.csv` | Downloaded once | Yes (small, 99 rows) |

`.gitignore` must exclude `instance/`, `ml/artifacts/`, `rag/index/`, `.env`, and must **stop** excluding `*.csv` globally (v1 bug). Use explicit paths instead of blanket `*.pkl` / `*.csv` rules.

## 4.2 Entity-relationship diagram

```
┌──────────────┐ 1      * ┌────────────────────┐ 1      * ┌──────────────────┐
│    users     │──────────│    predictions     │──────────│  chat_messages   │
└──────────────┘          └────────────────────┘          └──────────────────┘
        │ 1                                                        ▲
        └──────────────────────────────* ──────────────────────────┘
                                 (chat_messages.user_id)

┌────────────────────┐
│  contact_messages  │   (standalone; optional user_id)
└────────────────────┘
```

## 4.3 Tables

### 4.3.1 `users`

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PK, autoincrement | |
| `name` | VARCHAR(100) | NOT NULL | |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE, indexed | Stored lower-case, trimmed |
| `password_hash` | VARCHAR(255) | NOT NULL | Werkzeug `generate_password_hash` (scrypt default) |
| `preferred_language` | VARCHAR(5) | NOT NULL, default `'en'` | One of `en`, `te`, `ta`, `hi` |
| `created_at` | DATETIME | NOT NULL, default UTC now | |
| `last_login_at` | DATETIME | NULL | Updated on login |
| `is_active` | BOOLEAN | NOT NULL, default true | Flask-Login uses it |

### 4.3.2 `predictions`

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | |
| `user_id` | INTEGER | FK → users.id, NOT NULL, indexed, ON DELETE CASCADE | Ownership |
| `created_at` | DATETIME | NOT NULL, default UTC now, indexed | History ordering |
| `location` | VARCHAR(120) | NULL | Typed place name only |
| `weather_source` | VARCHAR(20) | NULL | `open-meteo` or `manual` |
| `temperature` | FLOAT | NOT NULL | °C |
| `humidity` | FLOAT | NOT NULL | % |
| `moisture` | FLOAT | NOT NULL | % |
| `soil_type` | VARCHAR(20) | NOT NULL | Must be in model meta |
| `crop_type` | VARCHAR(30) | NOT NULL | Must be in model meta |
| `nitrogen` | INTEGER | NOT NULL | 0–255 |
| `phosphorous` | INTEGER | NOT NULL | 0–255 |
| `potassium` | INTEGER | NOT NULL | 0–255 |
| `rating_n`, `rating_p`, `rating_k` | VARCHAR(6) | NOT NULL, default `'Medium'` | `Low` / `Medium` / `High` |
| `area_value` | FLOAT | NOT NULL | As entered |
| `area_unit` | VARCHAR(5) | NOT NULL | `acre` or `ha` |
| `fertilizer` | VARCHAR(20) | NOT NULL | Predicted class |
| `confidence` | FLOAT | NOT NULL | 0–1 |
| `top3_json` | TEXT | NOT NULL | `[{"label":"DAP","p":0.82}, ...]` |
| `ood_fields_json` | TEXT | NOT NULL, default `'[]'` | e.g. `["Nitrogen"]` |
| `dosage_json` | TEXT | NULL | Full dosage result (lines, schedule, notes) |
| `total_cost` | FLOAT | NULL | ₹ |
| `price_as_of` | VARCHAR(20) | NULL | From products JSON at calculation time |
| `model_version` | VARCHAR(40) | NOT NULL | From `model_meta.json` |

Indexes: `(user_id, created_at DESC)` for the history page.

### 4.3.3 `chat_messages`

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | |
| `user_id` | INTEGER | FK → users.id, NOT NULL, indexed, ON DELETE CASCADE | |
| `prediction_id` | INTEGER | FK → predictions.id, NOT NULL, indexed, ON DELETE CASCADE | Chat is always about one prediction |
| `role` | VARCHAR(10) | NOT NULL, CHECK in (`user`, `assistant`) | |
| `content` | TEXT | NOT NULL | Question or answer (max 500 chars for user) |
| `language` | VARCHAR(5) | NOT NULL | `en`/`te`/`ta`/`hi` |
| `sources_json` | TEXT | NOT NULL, default `'[]'` | `[{"source":"urea.md","heading":"Application","score":0.71}]` |
| `fallback` | BOOLEAN | NOT NULL, default false | True when the LLM failed and passages were returned |
| `latency_ms` | INTEGER | NULL | Assistant messages only |
| `model` | VARCHAR(60) | NULL | Gemini model used |
| `created_at` | DATETIME | NOT NULL, default UTC now | |

Index: `(prediction_id, created_at)`.

### 4.3.4 `contact_messages`

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `user_id` | INTEGER | FK → users.id, NULL |
| `name` | VARCHAR(100) | NOT NULL |
| `email` | VARCHAR(255) | NOT NULL |
| `message` | TEXT | NOT NULL, max 2000 chars |
| `created_at` | DATETIME | NOT NULL |

## 4.4 SQLAlchemy models (reference)

```python
# models.py
from datetime import datetime, timezone
from flask_login import UserMixin
from extensions import db

def utcnow():
    return datetime.now(timezone.utc)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    preferred_language = db.Column(db.String(5), nullable=False, default="en")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    predictions = db.relationship("Prediction", backref="user", lazy="dynamic",
                                  cascade="all, delete-orphan")

class Prediction(db.Model):
    __tablename__ = "predictions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    # ... remaining columns exactly as in §4.3.2 ...
    chats = db.relationship("ChatMessage", backref="prediction", lazy="dynamic",
                            cascade="all, delete-orphan", order_by="ChatMessage.created_at")

class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    __table_args__ = (db.CheckConstraint("role in ('user','assistant')", name="ck_chat_role"),)
    # ... columns as in §4.3.3 ...
```

Enable SQLite foreign keys on every connection (SQLite ignores `ON DELETE CASCADE` otherwise):

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def _fk_on(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()
```

## 4.5 Data access rules

1. Every query on `predictions` and `chat_messages` filters by `user_id = current_user.id`. Use a helper `get_owned_prediction_or_404(pid)`.
2. JSON columns are written with `json.dumps(..., ensure_ascii=False)` so Telugu/Tamil/Hindi text stays readable.
3. History uses `Prediction.query.filter_by(user_id=...).order_by(Prediction.created_at.desc()).paginate(page=p, per_page=10)`.
4. "Clear history" deletes the user's predictions (chats cascade) in one transaction.
5. Never store API keys, raw prompts with keys, or passwords outside `password_hash`.

## 4.6 Initialisation and migrations

- CLI command `flask --app app init-db` runs `db.create_all()` and prints the DB path.
- CLI command `flask --app app seed-demo` creates `demo@example.com` / `Demo@1234` and two sample predictions for the demo (development only; refuses when `FLASK_DEBUG=0` unless `--force`).
- Schema changes after the demo: adopt Flask-Migrate (Alembic). For tonight, `create_all()` on an empty DB is enough; delete `instance/app.db` to reset.

## 4.7 File-based stores

### 4.7.1 `data/crop_requirements.json`

```json
{
  "_meta": {"unit": "kg/ha", "basis": "typical general recommendations, India; verify with state package of practices", "version": "2026-11-06"},
  "Wheat": {
    "display": "Wheat",
    "rd": {"N": 120, "P2O5": 60, "K2O": 40},
    "n_split": [
      {"stage": "Basal (at sowing)", "pct": 50},
      {"stage": "First irrigation / crown root initiation (20–25 days)", "pct": 50}
    ],
    "avoid_chloride": false,
    "extra_notes": ["Apply zinc sulphate on zinc-deficient soils."]
  }
}
```

One entry per model crop: Barley, Cotton, Ground Nuts, Maize, Millets, Oil seeds, Paddy, Pulses, Sugarcane, Tobacco, Wheat. Values must match the crop documents in `knowledge_base/crops/`.

### 4.7.2 `data/fertilizer_products.json`

```json
{
  "_meta": {"currency": "INR", "price_as_of": "2026-03", "note": "Verify current MRP with local dealer before relying on cost"},
  "Urea":     {"N": 46, "P2O5": 0,  "K2O": 0,  "S": 0,  "bag_kg": 45, "price_per_bag": 266.50,  "price_verified": true},
  "DAP":      {"N": 18, "P2O5": 46, "K2O": 0,  "S": 0,  "bag_kg": 50, "price_per_bag": 1350.00, "price_verified": true},
  "MOP":      {"N": 0,  "P2O5": 0,  "K2O": 60, "S": 0,  "bag_kg": 50, "price_per_bag": 1710.54, "price_verified": true},
  "10-26-26": {"N": 10, "P2O5": 26, "K2O": 26, "S": 0,  "bag_kg": 50, "price_per_bag": 1814.82, "price_verified": true},
  "14-35-14": {"N": 14, "P2O5": 35, "K2O": 14, "S": 0,  "bag_kg": 50, "price_per_bag": 1700.00, "price_verified": false},
  "17-17-17": {"N": 17, "P2O5": 17, "K2O": 17, "S": 0,  "bag_kg": 50, "price_per_bag": 1500.00, "price_verified": false},
  "20-20":    {"N": 20, "P2O5": 20, "K2O": 0,  "S": 13, "bag_kg": 50, "price_per_bag": 1300.00, "price_verified": false},
  "28-28":    {"N": 28, "P2O5": 28, "K2O": 0,  "S": 0,  "bag_kg": 50, "price_per_bag": 1700.00, "price_verified": false},
  "SOP":      {"N": 0,  "P2O5": 0,  "K2O": 50, "S": 18, "bag_kg": 50, "price_per_bag": 3500.00, "price_verified": false}
}
```

Model class names (`"20-20"`, `"28-28"`) are used as keys so lookups need no mapping. MOP and SOP are not model classes; the dosage service uses them to fill potash gaps (SOP for chloride-sensitive crops such as tobacco). The UI shows "(approx.)" next to any price with `price_verified: false`. Price sources: DAP MRP ₹1,350/50 kg and 2025-26 average retail prices for MOP and 10-26-26 as reported in March 2026; urea statutory MRP ₹266.50/45 kg. Update these before the demo.

### 4.7.3 `rag/index/chunks.json` (generated)

```json
[{"id": 0, "source": "fertilizers/urea.md", "title": "Urea (46-0-0)", "heading": "How to apply", "applies_to": ["Urea"],
  "text": "Urea (46-0-0) — How to apply\nApply urea in split doses...", "char_count": 784}]
```

Row `i` in `chunks.json` corresponds to vector `i` in `faiss.index`.

## 4.8 Backup and reset

- Backup: copy `instance/app.db` (stop the app first) — a single file.
- Reset demo: delete `instance/app.db`, run `init-db` and `seed-demo`.
- Rebuild derived stores at any time: `python ml/train.py` and `python rag/build_index.py`.

## 4.9 Data retention and privacy

- Users can clear their history (predictions + chats).
- Deleting a user cascades to predictions and chats.
- No analytics or third-party trackers. Questions sent to Gemini contain the question, prediction context and knowledge-base passages, never the user's name or email.
