# 3. Architecture

How Smart Fertilizer Advisor is structured: components, folder layout, request flows, the ML and RAG pipelines, configuration, and the decisions behind them.

---

## 3.1 System context

```
                ┌──────────────────────────────────────────────────────────┐
  Browser  ───► │  Flask app (single process, local)                       │
  (Bootstrap,   │                                                          │
   chat.js,     │  Blueprints: core · auth · api                           │
   weather.js)  │  Services:   ml · dosage · rag · llm · weather · report  │
                │                                                          │
                │  Local files:  ml/artifacts/  rag/index/  data/*.json    │
                │  Database:     instance/app.db (SQLite)                  │
                └───────┬──────────────────────────┬───────────────────────┘
                        │ HTTPS                    │ HTTPS
                        ▼                          ▼
              Google Gemini API            Open-Meteo APIs
              - generate (answers,         - geocoding (place → lat/lon)
                translation)               - forecast (current temp, RH)
              - embed (gemini-embedding-001)
```

External dependencies are limited to Gemini and Open-Meteo; everything else runs locally.

## 3.2 Technology stack

| Layer | Choice | Why |
| --- | --- | --- |
| Web framework | Flask 3.x, Jinja2, application factory + blueprints | Keeps v1 templates; scales beyond one file |
| UI | Bootstrap 5.3 (stable), Bootstrap Icons, vanilla JS | Already used in v1; no build step |
| Auth | Flask-Login, Werkzeug password hashing | Simple session auth |
| Forms / CSRF | Flask-WTF (WTForms + CSRFProtect) | Validation + CSRF for forms and JSON POSTs |
| Rate limiting | Flask-Limiter (memory storage) | Protect login and chat |
| Database | SQLite via Flask-SQLAlchemy 3.x | Zero setup; file in `instance/` |
| ML | scikit-learn `Pipeline` (OneHotEncoder + RandomForestClassifier), joblib | One artifact, no train/serve skew |
| Embeddings | Gemini `gemini-embedding-001` (768 dims) | Multilingual retrieval (Telugu/Tamil/Hindi queries), no torch install |
| Vector store | FAISS `IndexFlatIP` on L2-normalised vectors; NumPy fallback | Exact cosine search; corpus is small |
| LLM | Gemini via `google-genai` SDK, model from `GEMINI_MODEL` (default `gemini-flash-latest`) | Free tier, fast, multilingual |
| Weather | Open-Meteo geocoding + forecast | No API key |
| PDF | fpdf2 + Noto Sans TTF fonts | Pure Python; Unicode with fonts |
| Config | python-dotenv + `config.py` classes | 12-factor style |
| Tests | pytest, pytest-mock | Offline, fast |

## 3.3 Folder layout (target)

```
fertilizer-prediction/
├── app.py                      # entry point: from app_factory import create_app; app = create_app()
├── app_factory.py              # create_app(config_name): extensions, blueprints, error handlers, services
├── config.py                   # BaseConfig / DevConfig / TestConfig
├── extensions.py               # db, login_manager, csrf, limiter instances
├── models.py                   # User, Prediction, ChatMessage, ContactMessage
├── forms.py                    # RegisterForm, LoginForm, PredictForm, ContactForm
├── blueprints/
│   ├── core.py                 # /, /dashboard, /predictor, /predict, /result/<id>, /history, /about, /contact, /report/<id>.pdf, /health
│   ├── auth.py                 # /register, /login, /logout
│   └── api.py                  # /api/chat, /api/chat/<prediction_id>, /api/weather, /api/predict
├── services/
│   ├── ml_service.py           # load pipeline + meta; predict(); options(); ood_check()
│   ├── dosage_service.py       # compute_dosage(crop, fertilizer, area, unit, ratings)
│   ├── llm_client.py           # Gemini wrapper: generate(), embed(), translate(); timeouts, retries
│   ├── rag_service.py          # VectorStore load/search; answer(question, context, language)
│   ├── weather_service.py      # geocode(place), current(lat, lon)
│   └── report_service.py       # build_pdf(prediction, chats) -> bytes
├── ml/
│   ├── train.py                # trains pipeline, writes artifacts/
│   ├── data/Fertilizer Prediction.csv
│   └── artifacts/              # fertilizer_pipeline.joblib, model_meta.json   (gitignored, built)
├── rag/
│   ├── build_index.py          # chunk knowledge_base/, embed, write index/
│   └── index/                  # faiss.index, chunks.json, index_meta.json    (gitignored, built)
├── knowledge_base/             # curated agronomy Markdown (RAG source)
├── data/
│   ├── crop_requirements.json  # RD N-P2O5-K2O kg/ha + split schedule per crop
│   └── fertilizer_products.json# nutrient %, bag size, price, price_as_of
├── static/
│   ├── css/style.css
│   ├── js/chat.js, js/weather.js, js/predictor.js
│   └── fonts/                  # NotoSans*.ttf for PDF (optional)
├── templates/
│   ├── base.html, index.html, dashboard.html, predictor.html, result.html,
│   │   history.html, about.html, contact.html
│   ├── auth/login.html, auth/register.html
│   ├── partials/_chat.html, partials/_dosage.html, partials/_pagination.html
│   └── errors/404.html, errors/500.html
├── tests/
│   ├── conftest.py, test_smoke.py, test_auth.py, test_ml.py,
│   │   test_dosage.py, test_rag.py, test_api.py, test_report.py
├── docs/                       # these 15 documents
├── instance/app.db             # SQLite (gitignored, created at first run)
├── .env.example, requirements.txt, AGENTS.md, README.md, .gitignore
```

## 3.4 Layering rules

```
templates / static JS
        │  (HTTP)
blueprints (routes)  ── validate input (forms), auth, call services, render/JSON
        │
services             ── business logic; no Flask request objects; pure functions where possible
        │
models / files / external APIs
```

- Routes never call Gemini, Open-Meteo, joblib or FAISS directly; only services do.
- Services receive plain values and return dataclasses/dicts, so they are unit-testable.
- Services are created once in `create_app()` and stored on `app.extensions["services"]`.

## 3.5 Key request flows

### 3.5.1 Prediction (POST → redirect → GET)

```
Browser ──POST /predict (form + CSRF)──► core.predict
  1. PredictForm.validate()                → field errors re-render predictor.html (400)
  2. ml_service.predict(features)          → {fertilizer, confidence, top3, ood_fields}
  3. dosage_service.compute_dosage(...)    → {lines[], total_cost, schedule[], area_ha}
  4. Prediction row saved (user_id)        → id
  5. 302 → /result/<id>
Browser ──GET /result/<id>──► core.result
  6. Load prediction (404 if not owner)    → render result.html with saved chats
```

The Post/Redirect/Get pattern prevents duplicate predictions on refresh and gives each result a shareable URL for history and PDF.

### 3.5.2 RAG chat

```
chat.js ──POST /api/chat {prediction_id, question, language} (X-CSRFToken)──► api.chat
  1. Auth + ownership check; rate limit 10/min/user
  2. Validate question (1–500 chars)
  3. rag_service.answer(question, prediction_context, language)
       a. q_embed = llm.embed(question, task="RETRIEVAL_QUERY")   (multilingual, no translation needed)
       b. hits = store.search(q_embed, k=4); keep score ≥ RAG_MIN_SCORE (0.55)
       c. if no hits → "I don't have information on that…" (localised), sources = []
       d. prompt = system rules + prediction context + numbered passages + question + language instruction
       e. text = llm.generate(prompt, timeout=15s)
       f. on LLM error/timeout → fallback: passages list, flag fallback=true
  4. Save user + assistant ChatMessage rows
  5. 200 {answer, sources[], language, fallback}
```

### 3.5.3 Weather auto-fill

```
weather.js ──GET /api/weather?q=Guntur──► api.weather
  1. weather_service.geocode(q, count=5)   → [] → 404 {error}
  2. if 1 match (or ?id= chosen) → current(lat, lon) → {temperature_c, humidity_pct, place, observed_at}
  3. if >1 match and no id → 200 {matches:[...]} for the user to pick
```

Results are cached in memory for 10 minutes per place to avoid repeat calls.

### 3.5.4 PDF report

```
GET /report/<id>.pdf → ownership check → report_service.build_pdf(prediction, last 5 chats) → send_file (application/pdf)
```

## 3.6 ML pipeline

**Training (`ml/train.py`)**

1. Load CSV; strip column whitespace (`"Humidity "` → `"Humidity"`); rename `Temparature` → `Temperature`.
2. Features: numeric `[Temperature, Humidity, Moisture, Nitrogen, Potassium, Phosphorous]`, categorical `[Soil Type, Crop Type]`.
3. `Pipeline([("prep", ColumnTransformer([("num","passthrough",num), ("cat", OneHotEncoder(handle_unknown="ignore"), cat)])), ("clf", RandomForestClassifier(n_estimators=300, random_state=42))])`.
4. Evaluate with `StratifiedKFold(n_splits=4, shuffle=True, random_state=42)`: accuracy mean and std, macro F1, per-class report, confusion matrix.
5. Fit on all rows; save `ml/artifacts/fertilizer_pipeline.joblib`.
6. Write `ml/artifacts/model_meta.json`:

```json
{
  "model_version": "2026.11.06-rf300",
  "algorithm": "RandomForestClassifier(n_estimators=300)",
  "sklearn_version": "1.x.y",
  "trained_at": "2026-11-06T18:00:00+05:30",
  "rows": 99,
  "features": ["Temperature","Humidity","Moisture","Soil Type","Crop Type","Nitrogen","Potassium","Phosphorous"],
  "classes": ["10-26-26","14-35-14","17-17-17","20-20","28-28","DAP","Urea"],
  "soil_types": ["Black","Clayey","Loamy","Red","Sandy"],
  "crop_types": ["Barley","Cotton","Ground Nuts","Maize","Millets","Oil seeds","Paddy","Pulses","Sugarcane","Tobacco","Wheat"],
  "ranges": {"Temperature":[25,38],"Humidity":[50,72],"Moisture":[25,65],"Nitrogen":[4,42],"Potassium":[0,19],"Phosphorous":[0,42]},
  "cv": {"folds": 4, "accuracy_mean": 0.96, "accuracy_std": 0.03, "f1_macro": 0.95},
  "feature_importance": {"Phosphorous":0.33,"Nitrogen":0.29}
}
```

Values above are illustrative; the script writes the real ones.

**Serving (`services/ml_service.py`)**

- Loads the pipeline and meta once at startup using paths resolved from the project root (never the CWD).
- `options()` returns soil and crop lists from meta, so forms can never offer an unknown label.
- `predict(dict)` builds a one-row DataFrame with the training column names, returns `predict_proba` top-3, top class, confidence, and `ood_fields` (inputs outside `ranges`).
- On startup, if the artifact is missing, the app still starts; `/health` reports `model_loaded: false`, and the predictor page shows "Model not trained — run `python ml/train.py`".
- Logs a warning if the runtime scikit-learn version differs from `meta.sklearn_version`.

## 3.7 RAG pipeline

**Indexing (`rag/build_index.py`)** — run whenever `knowledge_base/` changes:

1. Read every `*.md` under `knowledge_base/` except files starting with `_`.
2. Parse front matter (`title`, `category`, `tags`, `language`, `last_reviewed`).
3. Split by `##` headings; then pack paragraphs into chunks of about 800 characters with 150-character overlap; prefix each chunk with `"<title> — <heading>\n"` for context.
4. Embed in batches of up to 100 with `gemini-embedding-001`, `task_type=RETRIEVAL_DOCUMENT`, `output_dimensionality=768`.
5. L2-normalise; build `faiss.IndexFlatIP`; write `rag/index/faiss.index`.
6. Write `rag/index/chunks.json` (`id, source, title, heading, text, char_count`) and `index_meta.json` (embedding model, dims, chunk params, doc count, chunk count, built_at, KB content hash).

**Query (`services/rag_service.py`)**

| Parameter | Default (env) | Notes |
| --- | --- | --- |
| `RAG_TOP_K` | 4 | Passages sent to the LLM |
| `RAG_MIN_SCORE` | 0.55 | Cosine threshold; tune with test questions |
| `RAG_MAX_CONTEXT_CHARS` | 4000 | Hard cap on passage text in the prompt |
| `LLM_TIMEOUT_S` | 15 | Then fallback |
| `LLM_TEMPERATURE` | 0.2 | Factual tone |

Boosting: chunks whose `source` matches the predicted fertilizer or crop file get +0.05 score, so answers favour the user's context.

**Prompt template (summary)** — full text in Feature Development §10.4:

```
SYSTEM: You are an agricultural extension assistant. Answer ONLY from the numbered passages
and the farmer's context. If the passages do not contain the answer, say so. Keep answers under
150 words, practical, with numbers and units. Never invent doses. Cite passages as [1], [2].
Reply in {language_name}.
CONTEXT: crop, soil, NPK, fertilizer, confidence, dosage lines, out-of-range fields
PASSAGES: [1] (urea.md — Application) ... [4] ...
QUESTION: {question}
```

## 3.8 Configuration (`.env`)

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `SECRET_KEY` | Yes | — | Session signing; app refuses to start in non-debug without it |
| `FLASK_DEBUG` | No | `0` | Debug mode; never `1` on a network |
| `DATABASE_URL` | No | `sqlite:///app.db` (created in `instance/`) | SQLAlchemy URL |
| `GEMINI_API_KEY` | Yes for chat | — | Google AI Studio key |
| `GEMINI_MODEL` | No | `gemini-flash-latest` | Generation model |
| `GEMINI_EMBED_MODEL` | No | `gemini-embedding-001` | Embedding model |
| `RAG_TOP_K`, `RAG_MIN_SCORE`, `RAG_MAX_CONTEXT_CHARS` | No | 4, 0.55, 4000 | Retrieval tuning |
| `LLM_TIMEOUT_S`, `LLM_TEMPERATURE` | No | 15, 0.2 | Generation |
| `WEATHER_TIMEOUT_S` | No | 8 | Open-Meteo calls |
| `RATELIMIT_CHAT` | No | `10 per minute` | Chat limit per user |
| `PDF_FONT_DIR` | No | `static/fonts` | Noto TTF location |

## 3.9 Architecture decisions (ADR summary)

| # | Decision | Alternatives considered | Reason |
| --- | --- | --- | --- |
| AD1 | Keep Flask + Jinja, add blueprints and services | FastAPI + React | Fastest path from v1; no frontend build |
| AD2 | Gemini embeddings instead of local sentence-transformers | all-MiniLM-L6-v2 | Multilingual queries work without translation; avoids ~1–2 GB torch install |
| AD3 | FAISS flat index with NumPy fallback | Chroma, pgvector | Corpus is a few hundred chunks; exact search is instant; fewer dependencies |
| AD4 | SQLite + SQLAlchemy | Postgres, JSON files | Zero setup, relational history, easy to switch via `DATABASE_URL` |
| AD5 | sklearn Pipeline with one-hot encoding saved via joblib | Separate LabelEncoders + pickle | Prevents feature-order and encoding drift; one artifact |
| AD6 | Dosage is rule-based, not ML | Regression model | Transparent, explainable, uses standard agronomy; no labelled dosage data |
| AD7 | Prices and crop requirements in JSON | Hard-coded / DB | Editable without code changes before the demo |
| AD8 | Post/Redirect/Get for predictions | Render result from POST | No duplicate saves; stable URLs for history and PDF |
| AD9 | LLM failure → retrieval-only fallback | Error message | Demo never dead-ends |

## 3.10 Cross-cutting concerns

- **Logging:** `logging` to console, INFO by default; log prediction latency, chat latency, retrieval scores, LLM errors (never log API keys or passwords).
- **Error handling:** custom 404/500 pages; JSON APIs return `{"error": {"code", "message"}}` with proper status codes.
- **Time zone:** store UTC in DB; display Asia/Kolkata.
- **Versioning:** `model_version` and `index_meta.built_at` stored on each prediction/chat for traceability.
