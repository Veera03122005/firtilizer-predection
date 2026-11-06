# 9. Setup

Everything needed to get Smart Fertilizer Advisor running on a laptop: prerequisites, dependencies, environment variables, build steps, and Windows/macOS/Linux notes.

---

## 9.1 Prerequisites

| Item | Version / note |
| --- | --- |
| Python | 3.10, 3.11 or 3.12 (64-bit) |
| Git | Any recent version |
| Antigravity IDE | For agent-assisted development (optional for running) |
| Internet | Needed for `pip install`, `build_index.py`, chat (Gemini) and weather (Open-Meteo) |
| Gemini API key | Free from Google AI Studio → "Get API key" |
| Disk | ~600 MB for the virtual environment |

## 9.2 Clone and create the environment

```bash
git clone <your-fork-url> fertilizer-advisor
cd fertilizer-advisor
git checkout -b v2-advisor

python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows cmd
.venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt
```

PowerShell blocks activation scripts by default; if so run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 9.3 `requirements.txt`

```text
# Web
Flask>=3.0,<4
Flask-Login>=0.6.3
Flask-WTF>=1.2
email-validator>=2.1
Flask-SQLAlchemy>=3.1
Flask-Limiter>=3.5
python-dotenv>=1.0

# ML
scikit-learn>=1.4
pandas>=2.1
numpy>=1.26
joblib>=1.3

# RAG / LLM
google-genai>=1.0
faiss-cpu>=1.8

# Integrations
requests>=2.31
fpdf2>=2.7
uharfbuzz>=0.39        # optional: correct Telugu/Tamil/Hindi shaping in PDFs

# Tests
pytest>=8.0
pytest-mock>=3.12
```

After a working install, freeze exact versions for reproducibility:

```bash
pip freeze > requirements.lock
```

The model artifact records the scikit-learn version; retrain (`python ml/train.py`) whenever scikit-learn changes.

If `faiss-cpu` fails to install (rare on very new Python versions), remove it; `rag_service` falls back to NumPy cosine search automatically.

## 9.4 Environment variables

Create `.env` from the template and fill the two required values.

```bash
cp .env.example .env        # Windows: copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste as SECRET_KEY
```

`.env.example`:

```dotenv
# Required
SECRET_KEY=change-me-to-a-64-char-random-hex
GEMINI_API_KEY=

# Flask
FLASK_DEBUG=0
DATABASE_URL=sqlite:///app.db

# Gemini
GEMINI_MODEL=gemini-flash-latest
GEMINI_EMBED_MODEL=gemini-embedding-001
LLM_TIMEOUT_S=15
LLM_TEMPERATURE=0.2

# RAG
RAG_TOP_K=4
RAG_MIN_SCORE=0.55
RAG_MAX_CONTEXT_CHARS=4000

# Integrations
WEATHER_TIMEOUT_S=8
PDF_FONT_DIR=static/fonts

# Rate limits
RATELIMIT_CHAT=10 per minute
```

Notes:

- With Flask-SQLAlchemy 3.x, a relative SQLite path like `sqlite:///app.db` is created inside the app's `instance/` folder.
- Do not set both `GEMINI_API_KEY` and `GOOGLE_API_KEY`; the SDK prefers `GOOGLE_API_KEY` if both exist.
- `.env` is in `.gitignore`. Never commit it.

## 9.5 Data and build steps

```bash
# 1. Training data (99 rows) — put the CSV here:
#    ml/data/Fertilizer Prediction.csv
python ml/train.py
#    → ml/artifacts/fertilizer_pipeline.joblib, ml/artifacts/model_meta.json, prints CV metrics

# 2. Knowledge base index (needs GEMINI_API_KEY, ~1 minute)
python rag/build_index.py
#    → rag/index/faiss.index, chunks.json, index_meta.json; prints doc and chunk counts

# 3. Database
flask --app app init-db
flask --app app seed-demo     # demo@example.com / Demo@1234

# 4. Optional: fonts for Telugu/Tamil/Hindi in PDFs
#    Download from Google Fonts and place the .ttf files in static/fonts/:
#    NotoSans-Regular.ttf, NotoSansTelugu-Regular.ttf, NotoSansTamil-Regular.ttf, NotoSansDevanagari-Regular.ttf

# 5. Run
flask --app app run           # http://127.0.0.1:5000
```

Re-run step 2 whenever you edit `knowledge_base/`. Re-run step 1 whenever the dataset or scikit-learn version changes.

## 9.6 Verify the install

```bash
curl -s http://127.0.0.1:5000/health
pytest -q
```

Expected `/health`: `model_loaded: true`, `rag_index_loaded: true`, `llm_configured: true`, `db: "ok"`.

## 9.7 Running in Antigravity

1. File → Open Folder → the repo.
2. Select the `.venv` interpreter (Python: Select Interpreter).
3. Use the integrated terminal for the commands above.
4. Agent conversations: one per phase (Project Implementation §8.5). The agent reads `AGENTS.md` automatically.
5. Optional MCP servers for the agent: see `docs/12-MCP-CONNECTION.md`.

## 9.8 Demo-day checklist

- [ ] Laptop charged; mobile hotspot ready as backup internet
- [ ] `.env` has a working key (test one chat question 10 minutes before)
- [ ] Fresh DB seeded (`del instance\app.db` / `rm instance/app.db`, then `init-db`, `seed-demo`)
- [ ] Index built from the final knowledge base
- [ ] Browser zoom 110–125 % for the projector; close other tabs
- [ ] `FLASK_DEBUG=0`
- [ ] Demo script (Testing & QA §14.6) rehearsed twice

## 9.9 Optional: run with gunicorn (Linux/macOS)

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:8000 "app:app"
```

With several workers, keep `SECRET_KEY` fixed in `.env` (sessions break otherwise) and use a shared rate-limit storage (Redis) instead of memory if exposed publicly.
