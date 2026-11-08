# 🌱 Smart Fertilizer Advisor


A Flask web app that recommends a fertilizer from soil, crop and weather inputs, calculates how much to apply and what it costs, and lets farmers ask follow-up questions to an AI assistant that answers from a curated agronomy knowledge base in English, Telugu, Tamil or Hindi.

Built on [vivekg189/Fertilizer-prediction](https://github.com/vivekg189/Fertilizer-prediction) (v1), with the v1 defects fixed and new features added.

---

## Features

| Feature | Description |
| --- | --- |
| Fertilizer prediction | Random-forest pipeline over 8 inputs; shows confidence, top-3 alternatives and warns when inputs are outside the training range |
| Dosage & cost | kg/ha, kg for your farm, bags and ₹ cost per product (DAP / Urea / MOP / complexes), adjusted for Soil Health Card ratings |
| Application schedule | Basal and top-dressing split per crop |
| Ask the Advisor (RAG) | Gemini answers grounded in `knowledge_base/` with cited sources; falls back to retrieved passages if the AI service is unavailable |
| Multilingual answers | English, తెలుగు, தமிழ், हिन्दी |
| Weather auto-fill | Temperature and humidity from a place name via Open-Meteo (no key) |
| PDF report | Recommendation, dosage, schedule and Q&A in one printable file |
| Accounts & history | Register/login; predictions and chats saved per user in SQLite |

## Screens

Home → Login → Predictor (with "Get weather") → Result (recommendation, dosage, schedule, chat) → History → PDF.

## Tech stack

Flask 3 · Jinja2 · Bootstrap 5.3 · Flask-Login · Flask-WTF · Flask-Limiter · Flask-SQLAlchemy (SQLite) · scikit-learn · pandas · joblib · Google Gemini (`google-genai`) · FAISS · Open-Meteo · fpdf2 · pytest

## Architecture

```
Browser ─► Flask (blueprints: core, auth, api)
              ├─ ml_service      → scikit-learn pipeline (ml/artifacts)
              ├─ dosage_service  → data/crop_requirements.json, data/fertilizer_products.json
              ├─ rag_service     → FAISS index (rag/index) + Gemini
              ├─ weather_service → Open-Meteo
              ├─ report_service  → fpdf2 PDF
              └─ SQLite (instance/app.db)
```

Details: [docs/03-ARCHITECTURE.md](docs/03-ARCHITECTURE.md).

## Quick start

Prerequisites: Python 3.10+, internet, a free Gemini API key from [Google AI Studio](https://aistudio.google.com/).

```bash
git clone <your-fork-url> fertilizer-advisor && cd fertilizer-advisor
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
# edit .env → set SECRET_KEY and GEMINI_API_KEY

python ml/train.py                 # train model → ml/artifacts/
python rag/build_index.py          # embed knowledge base → rag/index/
flask --app app init-db
flask --app app seed-demo          # demo@example.com / Demo@1234
flask --app app run
```

Open http://127.0.0.1:5000 and log in with the demo account.

Full setup, Windows notes and troubleshooting: [docs/09-SETUP.md](docs/09-SETUP.md).

## Project structure

```
app.py, app_factory.py, config.py, extensions.py, models.py, forms.py
blueprints/   core.py · auth.py · api.py
services/     ml_service · dosage_service · llm_client · rag_service · weather_service · report_service
ml/           train.py · data/ · artifacts/ (built)
rag/          build_index.py · index/ (built)
knowledge_base/  agronomy documents used by the chat
data/         crop_requirements.json · fertilizer_products.json
templates/ · static/ · tests/ · docs/
```

## Model card (summary)

| Item | Value |
| --- | --- |
| Algorithm | RandomForestClassifier (300 trees) in a scikit-learn Pipeline with one-hot encoding |
| Data | Public "Fertilizer Prediction" dataset, 99 rows, 7 classes |
| Validation | 4-fold stratified CV; the About page shows the exact score from `ml/artifacts/model_meta.json` (≈ 96% in our runs) |
| Strongest signals | Phosphorous, Nitrogen, Potassium |
| Limitations | Very small dataset; N/P/K values are dataset index values, not lab kg/ha; temperature, humidity, moisture, soil and crop contribute little; results outside the training ranges are less reliable |

## Testing

```bash
pytest -q
```

Tests run offline (Gemini and Open-Meteo are mocked). See [docs/14-TESTING-QA.md](docs/14-TESTING-QA.md).

## Documentation

| # | Document |
| --- | --- |
| 1 | [PRD](docs/01-PRD.md) |
| 2 | [Design](docs/02-DESIGN.md) |
| 3 | [Architecture](docs/03-ARCHITECTURE.md) |
| 4 | [Database](docs/04-DATABASE.md) |
| 5 | [API](docs/05-API.md) |
| 6 | [Agents](docs/06-AGENTS.md) (copy at repo root as `AGENTS.md`) |
| 7 | README (this file) |
| 8 | [Project Implementation](docs/08-PROJECT-IMPLEMENTATION.md) |
| 9 | [Setup](docs/09-SETUP.md) |
| 10 | [Feature Development](docs/10-FEATURE-DEVELOPMENT.md) |
| 11 | [Authentication & Security](docs/11-AUTHENTICATION-SECURITY.md) |
| 12 | [MCP Connection](docs/12-MCP-CONNECTION.md) |
| 13 | [Integrations](docs/13-INTEGRATIONS.md) |
| 14 | [Testing & QA](docs/14-TESTING-QA.md) |
| 15 | [Debugging](docs/15-DEBUGGING.md) |


## Disclaimer

Educational project. Doses and prices are approximate and based on general recommendations. Always confirm with a soil test and your local agriculture officer or Krishi Vigyan Kendra before applying fertilizer.

## License

MIT — add a `LICENSE` file with the MIT text and your name/year.
