# 15. Debugging

How to diagnose problems quickly: logging, tools, a table of known errors with fixes, and a prompt template for asking the Antigravity agent to debug.

---

## 15.1 First steps for any problem

1. Read the **terminal** running Flask: the traceback's last lines name the file, line and exception.
2. Check `/health`: which component is down (model, index, LLM, DB)?
3. Open browser DevTools → Console and Network for front-end/API errors (status code + JSON `error.code`).
4. Reproduce with the smallest input; write it down.
5. Run `pytest -q`: did a test start failing?

## 15.2 Logging

```python
# app_factory.py
import logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
```

What each service logs:

| Logger | INFO | WARNING / ERROR |
| --- | --- | --- |
| `services.ml_service` | Model version loaded | Missing artifacts, sklearn version mismatch |
| `services.rag_service` | Chunks loaded, per-question top scores and latency | Index/config mismatch, no hits |
| `services.llm_client` | Model used, latency | API errors with code, retries, fallbacks |
| `services.weather_service` | Cache hit/miss | HTTP errors, empty results |
| `blueprints.*` | — | Validation failures (fields only), 404 ownership misses |

Set `LOG_LEVEL=DEBUG` temporarily for more detail. Never log passwords, API keys, full prompts in production, or session cookies.

## 15.3 Tools

| Tool | Use |
| --- | --- |
| Antigravity debugger (Python) | Breakpoints in services; launch `flask --app app run --no-reload` so breakpoints hit |
| `flask --app app shell` | Inspect DB (`Prediction.query.all()`), call services directly |
| `sqlite3 instance/app.db` or the SQLite MCP server | Check rows, foreign keys (`PRAGMA foreign_keys;`) |
| `python -c "from services.ml_service import MLService; print(MLService().options())"` | Model loading without Flask |
| `python rag/build_index.py --dry-run` | Show chunk counts and sizes without calling Gemini |
| `python -m json.tool <file>` | Validate JSON (data files, MCP config) |
| Browser DevTools | Network tab for `/api/chat` payloads and timings |

## 15.4 Known errors and fixes

### Startup / configuration

| Symptom | Cause | Fix |
| --- | --- | --- |
| `RuntimeError: SECRET_KEY is not set` | `.env` missing or not loaded | Create `.env` from `.env.example`; run from the repo root |
| `ModuleNotFoundError: No module named 'services'` | Running a script from a sub-folder | Run from the repo root, or `python -m ml.train` style |
| Logged out after every restart | `SECRET_KEY` changes on start | Fixed key in `.env` |
| `/health` shows `model_loaded: false` | Artifacts not built / wrong path | `python ml/train.py`; paths must be project-root based |
| `InconsistentVersionWarning` from scikit-learn | Model trained with another sklearn version | Retrain with the installed version |
| `TemplateNotFound: history.html` | Template missing (v1 bug) | Create the template (Phase 1/2) |

### Prediction

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ValueError: y contains previously unseen labels` | Old LabelEncoder code with a crop not in data (e.g., "Rice") | Use the new pipeline; build dropdowns from meta |
| `ValueError: columns are missing` | DataFrame columns differ from training names | Use the exact `FEATURES` list (Feature Dev §10.2) |
| All predictions the same class | NPK entered far outside training range | Expected; OOD warning shown. Use in-range sample values for demo |
| Form always invalid | CSRF token missing in template | Add `{{ form.hidden_tag() }}` |

### Database

| Symptom | Cause | Fix |
| --- | --- | --- |
| `sqlite3.OperationalError: no such table` | DB not initialised / wrong file | `flask --app app init-db`; check `DATABASE_URL` |
| Chats remain after deleting a prediction | SQLite foreign keys off | Add the `PRAGMA foreign_keys=ON` listener (Database §4.4) |
| `database is locked` | Another process (DB browser, MCP server) holds a write lock | Close it; use a copy for MCP inspection |
| `IntegrityError: UNIQUE constraint failed: users.email` | Duplicate registration not caught in form | Validate uniqueness in `RegisterForm` before insert |

### RAG / Gemini

| Symptom | Cause | Fix |
| --- | --- | --- |
| Every chat answer is the fallback | Invalid/missing key, model name wrong, or quota | Check logs for the API error code; test the key with a one-line script (§15.6) |
| `403 PERMISSION_DENIED` | Key revoked or from the wrong project | Create a new key in AI Studio |
| `429 RESOURCE_EXHAUSTED` | Free-tier rate limit | Wait a minute; reduce demo retries; lower chat rate |
| `404 model not found` | `GEMINI_MODEL` value outdated | Set `gemini-flash-latest` or a model ID listed in AI Studio |
| Answers ignore the knowledge base | Index empty/stale; threshold too low | Rebuild index; check `/health` `rag_chunks`; look at logged scores |
| Always "I don't have information" | `RAG_MIN_SCORE` too high, or index built with a different embedding model | Lower to 0.45–0.5 and test; rebuild index after model/dims change |
| Wrong language answer | Language not passed / rule 8 missing | Check request payload `language` and system prompt |
| `ImportError: faiss` (Windows) | Wheel unavailable | NumPy fallback runs automatically; or `pip install faiss-cpu` in a Python version with wheels |
| Index loads but scores near 0 | Vectors not normalised | Normalise at build and query time |
| Chat button does nothing; Console shows 400 | Missing `X-CSRFToken` header | Read token from `<meta name="csrf-token">` |

### Weather

| Symptom | Cause | Fix |
| --- | --- | --- |
| "No place found" for a village | Not in the geocoding database | Try the nearest town or district name |
| 502 from `/api/weather` | No internet / Open-Meteo issue | Manual entry; check connectivity |
| Wrong place filled | Several matches, first one auto-picked | UI must show the picker when > 1 match |

### PDF

| Symptom | Cause | Fix |
| --- | --- | --- |
| `FPDFUnicodeEncodingException` / boxes instead of text | Core font used for non-Latin text | Register Noto TTF fonts; use them for those cells |
| Telugu letters in wrong order | No text shaping | `pip install uharfbuzz`, `pdf.set_text_shaping(True)` |
| Blank download / 0-byte file | Returned `pdf.output()` incorrectly | `bytes(pdf.output())` into `BytesIO`, then `send_file` |

### Front end

| Symptom | Cause | Fix |
| --- | --- | --- |
| Page unstyled | CDN blocked/offline or SRI hash mismatch | Use local `static/vendor/` copies; recopy integrity hash |
| Inline script blocked | CSP from Security §11.10 | Move scripts to `static/js/` |
| Chat shows HTML tags literally / or executes them | Rendering choice | Must show literally: use `textContent` (correct behaviour) |

## 15.5 Debugging recipes

**Trace one chat request**
1. DevTools → Network → `/api/chat` → check request JSON and response.
2. Server log: retrieval scores and sources for that question, LLM latency/error.
3. In `flask shell`: `rag = app.extensions["services"]["rag"]; [ (h.chunk["source"], h.score) for h in rag.search("when to apply urea", 4, set()) ]`.
4. If retrieval is right but the answer is wrong, print the built prompt (DEBUG level) and adjust the knowledge-base text, not the rules.

**Check a dosage number**
```python
from services.dosage_service import compute_dosage
compute_dosage("Wheat", "DAP", 2, "acre", {})
```
Compare with Feature Development §10.3.4.

## 15.6 Quick key test

```python
# scripts/check_gemini.py — run: python scripts/check_gemini.py
import os
from dotenv import load_dotenv
from google import genai
load_dotenv()
c = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
print(c.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"), contents="Say OK").text)
print(len(c.models.embed_content(model="gemini-embedding-001", contents="test").embeddings[0].values))
```

## 15.7 Resetting to a clean state

```bash
rm -f instance/app.db                 # Windows: del instance\app.db
rm -rf rag/index ml/artifacts         # Windows: rmdir /s /q rag\index ml\artifacts
python ml/train.py && python rag/build_index.py
flask --app app init-db && flask --app app seed-demo
```

## 15.8 Prompt template: asking the Antigravity agent to debug

```text
Read AGENTS.md and docs/15-DEBUGGING.md.

Problem: <one sentence>
Steps to reproduce:
1. ...
Expected: ...
Actual: ...
Full error / traceback:
<paste exactly>
Relevant log lines:
<paste>
What I already tried: ...

Please: (1) explain the root cause in 2–3 sentences, citing the file and line; (2) propose the smallest fix
consistent with docs/03-ARCHITECTURE.md and AGENTS.md invariants; (3) add or update a test that fails before
the fix and passes after; (4) run pytest -q and show the result. Do not change unrelated files.
```
