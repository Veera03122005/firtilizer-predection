# AGENTS.md — Instructions for AI coding agents

> Copy this file to the repository root as `AGENTS.md`. Antigravity and other coding agents read it before making changes. Keep it short enough to be read every time; details live in `docs/`.

## Project in one paragraph

Smart Fertilizer Advisor is a Flask 3 web app. A logged-in user enters soil, crop, nutrient and weather values; a scikit-learn pipeline predicts one of 7 fertilizers; a rule-based service computes dosage and cost; a RAG chat (Gemini + FAISS over `knowledge_base/`) explains the result in English, Telugu, Tamil or Hindi; a PDF report can be downloaded. Data is stored in SQLite. Specs: `docs/01-PRD.md` (what), `docs/03-ARCHITECTURE.md` (how), `docs/05-API.md` (contracts), `docs/04-DATABASE.md` (schema).

## Golden rules

1. **Read the relevant doc before coding.** PRD for behaviour, ARCHITECTURE for where code goes, API for request/response shapes, DATABASE for columns. If code and docs disagree, stop and ask; do not silently pick one.
2. **One task at a time.** Implement only the task in the current prompt. Do not refactor unrelated files.
3. **Run tests after every change:** `pytest -q`. Do not finish a task with failing tests. Add or update tests for what you changed.
4. **Never commit secrets.** API keys live in `.env` only. Never print, log or hard-code `GEMINI_API_KEY` or `SECRET_KEY`. Never write keys into docs, tests or code comments.
5. **Never enable debug by default.** `FLASK_DEBUG` defaults to `0`.
6. **Keep the stack.** Flask + Jinja + Bootstrap 5 + vanilla JS. No React, no Tailwind, no new database, no new web framework.
7. **Ask before adding a dependency.** If you must add one, pin it in `requirements.txt` and say why.

## Where things go

| Concern | Location | Rule |
| --- | --- | --- |
| Routes | `blueprints/core.py`, `auth.py`, `api.py` | Thin: validate → call service → render/JSON |
| Business logic | `services/*.py` | No `flask.request` inside services; plain inputs/outputs |
| External calls (Gemini, Open-Meteo) | `services/llm_client.py`, `services/weather_service.py` only | Timeouts on every call; catch and convert errors |
| DB models | `models.py` | Columns exactly as `docs/04-DATABASE.md` |
| Forms/validation | `forms.py` (Flask-WTF) | Server-side validation is mandatory; JS validation is only UX |
| Config | `config.py` reading `.env` | Every new setting gets a default and a row in ARCHITECTURE §3.8 |
| Reference data | `data/*.json` | Doses and prices are never hard-coded in Python |
| Templates | `templates/`, partials in `templates/partials/` | Extend `base.html`; reuse existing CSS classes |

## Invariants — do not break these

- **ML input columns** are exactly `Temperature, Humidity, Moisture, Soil Type, Crop Type, Nitrogen, Potassium, Phosphorous` (note Potassium before Phosphorous, as in the dataset). Build a DataFrame with these names; never a positional NumPy array.
- **Dropdown options** for soil and crop come from `model_meta.json` (`soil_types`, `crop_types`). Never hard-code lists. Display "Paddy" as "Paddy (Rice)" but submit `Paddy`.
- **Model artifact** is loaded from a path relative to the project root (`Path(__file__).resolve().parent...`), never the current working directory.
- **Ownership:** every query on `Prediction` / `ChatMessage` filters by `current_user.id`; not-owned → 404.
- **CSRF** on every POST, including `fetch` calls (header `X-CSRFToken`).
- **Chat never 500s.** Any Gemini error/timeout returns the retrieval-only fallback (`fallback: true`).
- **RAG answers only from retrieved passages**; the system prompt in `docs/10-FEATURE-DEVELOPMENT.md` §10.4 is the source of truth. Do not loosen it.
- **Dosage algorithm** is the one in Feature Development §10.3. The worked example (Wheat, 2 acres, Medium ratings → DAP 105.6 kg, MOP 54.0 kg, Urea 169.8 kg, ₹5,702) must stay a passing test.
- **User-facing errors** are friendly messages; stack traces only in logs.
- **UTF-8 everywhere**: `json.dumps(..., ensure_ascii=False)`, `<meta charset="utf-8">`, PDF fonts for Indic scripts.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # then fill SECRET_KEY, GEMINI_API_KEY
python ml/train.py                                       # builds ml/artifacts/
python rag/build_index.py                                # builds rag/index/ (needs GEMINI_API_KEY)
flask --app app init-db && flask --app app seed-demo     # creates instance/app.db + demo user
flask --app app run                                      # http://127.0.0.1:5000
pytest -q                                                # all tests, offline
```

## Testing rules

- Tests must run **offline**: mock `llm_client` and `weather_service` (see `tests/conftest.py` fixtures `fake_llm`, `fake_weather`).
- Use the `TestConfig` (in-memory SQLite, CSRF disabled only in tests, `WTF_CSRF_ENABLED=False`).
- Add a test for every bug you fix, named after the bug (`test_rice_not_offered_paddy_is`).
- The smoke test hits every route in `docs/05-API.md` and asserts the documented status code.

## Style

- Python 3.10+, PEP 8, type hints on service functions, docstrings on public functions.
- f-strings; `logging.getLogger(__name__)`, not `print`.
- Small functions (< 40 lines). No bare `except:`; catch specific exceptions.
- Jinja: no business logic in templates beyond formatting and loops.
- JS: vanilla ES2020, no inline `onclick`; one file per feature in `static/js/`.
- Commit messages: `feat:`, `fix:`, `docs:`, `test:`, `refactor:` + short summary.

## When you are unsure

Stop and ask the human with a short question and your proposed default. Do not guess on: dose numbers, prices, agronomy facts, security settings, database schema changes, or deleting files.

## Definition of done (every task)

- [ ] Code follows the layering and invariants above
- [ ] `pytest -q` passes; new behaviour has tests
- [ ] No secrets, debug flags or print statements added
- [ ] Docs updated if behaviour, API or schema changed
- [ ] Manually checked the page/endpoint in the browser
