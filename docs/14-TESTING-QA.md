# 14. Testing & QA

Test strategy, automated test suite, manual checklist, RAG evaluation and the demo script.

---

## 14.1 Strategy

| Level | Tool | Scope | Runs |
| --- | --- | --- | --- |
| Unit | pytest | Services: ML, dosage, RAG (chunking, search, prompt), weather parsing, PDF | Every change |
| Integration | pytest + Flask test client | Routes, auth, ownership, DB writes, JSON contracts | Every change |
| Contract | pytest | Response shapes match `docs/05-API.md` examples | Every change |
| Manual | Checklist §14.5 | UI, layout, languages, PDFs | End of each phase |
| RAG evaluation | `tests/rag_eval.py` (live, optional) | Retrieval hits and answer quality on fixed questions | Before demo |
| Demo rehearsal | Script §14.6 | Full story end to end | Twice before the review |

All automated tests are **offline**: Gemini and Open-Meteo are mocked. Target: < 30 s total, ≥ 80 % line coverage of `services/`.

## 14.2 Test setup

```python
# tests/conftest.py
import pytest
from app_factory import create_app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

class FakeLLM:
    enabled = True
    def __init__(self): self.fail = False; self.last_prompt = None
    def embed(self, texts, task_type, dims=768):
        import numpy as np
        out = []
        for t in texts:                       # deterministic bag-of-letters vectors
            v = np.zeros(dims)
            for ch in t.lower():
                v[ord(ch) % dims] += 1
            out.append(list(v))
        return out
    def generate(self, system, user, max_tokens=600):
        from services.llm_client import LLMError
        if self.fail: raise LLMError("simulated")
        self.last_prompt = (system, user)
        return "Apply DAP at sowing as a basal dose [1]. Please confirm with your local agriculture officer."

@pytest.fixture
def app(tmp_path):
    app = create_app("testing")               # in-memory SQLite, CSRF off, rate limits off
    with app.app_context():
        db.create_all()
        yield app

@pytest.fixture
def fake_llm(app):
    llm = FakeLLM()
    app.extensions["services"]["llm"] = llm
    app.extensions["services"]["rag"].llm = llm
    return llm

@pytest.fixture
def client(app): return app.test_client()

@pytest.fixture
def user(app):
    u = User(name="Test", email="t@example.com", password_hash=generate_password_hash("Passw0rd!"))
    db.session.add(u); db.session.commit(); return u

@pytest.fixture
def auth_client(client, user):
    client.post("/login", data={"email": "t@example.com", "password": "Passw0rd!"})
    return client
```

`TestConfig`: `TESTING=True`, `SQLALCHEMY_DATABASE_URI="sqlite://"`, `WTF_CSRF_ENABLED=False`, `RATELIMIT_ENABLED=False`, `SECRET_KEY="test"`, and a small test RAG index built from `tests/fixtures/kb/` with `FakeLLM` embeddings.

## 14.3 Automated test catalogue

### `test_smoke.py`

| Test | Assert |
| --- | --- |
| Public pages `/`, `/about`, `/contact`, `/login`, `/register` | 200 |
| Protected pages anonymous `/dashboard`, `/predictor`, `/history` | 302 to `/login?next=…` |
| Protected pages logged in | 200 |
| `/health` | 200 and keys `model_loaded`, `rag_index_loaded`, `llm_configured`, `db` |
| Unknown URL | 404 custom page, no stack trace |

### `test_ml.py`

| Test | Assert |
| --- | --- |
| `test_options_from_meta` | 11 crops incl. "Paddy", no "Rice"; 5 soils |
| `test_predict_paddy` | Returns a class in meta classes; confidence 0–1; top3 length 3 |
| `test_urea_pattern` | N 37, P 0, K 0 → "Urea" |
| `test_dap_pattern` | N 12, P 36, K 0 → "DAP" |
| `test_ood_detection` | N 80 → `"Nitrogen"` in `ood_fields` |
| `test_feature_order` | Pipeline `feature_names_in_` equals the documented column list |

### `test_dosage.py`

All seven cases in Feature Development §10.3.4–10.3.5, with prices loaded from `tests/fixtures/fertilizer_products.json`. Use `pytest.approx(abs=0.1)` for kg and `abs=1` for ₹. Plus:

| Test | Assert |
| --- | --- |
| `test_hectare_unit` | 1 ha gives kg_total = kg_per_ha |
| `test_tobacco_uses_sop` | No MOP line; note present |
| `test_schedule_sums_to_total_urea` | Sum of urea across stages = urea kg_total (±0.2) |
| `test_unknown_crop_raises` | `KeyError`/custom error |

### `test_auth.py`

| Test | Assert |
| --- | --- |
| Register success | 302 to dashboard; user in DB; password hashed (not equal to plain) |
| Duplicate email (different case) | Form error |
| Weak password | Form error |
| Login wrong password | 401 + generic message |
| `next` open-redirect `//evil.com` | Redirects to dashboard instead |
| Logout via GET | 405 |
| CSRF enabled test | POST `/login` without token → 400 |

### `test_core.py`

| Test | Assert |
| --- | --- |
| POST `/predict` valid | 302 → `/result/<id>`; Prediction saved with user_id, dosage_json, total_cost |
| POST `/predict` invalid crop "Rice" | 400; error message; nothing saved |
| Result of another user | 404 |
| History pagination | 12 rows → page 1 has 10, page 2 has 2 |
| Clear history | Only current user's rows deleted; chats cascade |

### `test_api.py`

| Test | Assert |
| --- | --- |
| Chat valid | 200; keys `answer, sources, language, fallback, message_id`; 2 ChatMessage rows |
| Chat fallback | `fake_llm.fail=True` → 200, `fallback: true`, answer starts with fallback text |
| Chat empty / 501-char question | 400 `VALIDATION_ERROR` |
| Chat invalid language `fr` | 400 |
| Chat other user's prediction | 404 |
| Chat anonymous | 401 JSON |
| Chat history GET | Messages ordered oldest first |
| Weather single match | Mock geocode 1 result → fields `temperature_c`, `humidity_pct` |
| Weather multiple | `matches` list |
| Weather not found | 404 |
| Weather upstream error | 502 |

### `test_rag.py`

| Test | Assert |
| --- | --- |
| Chunking | No chunk > 800 chars; overlap present; `_INDEX.md` skipped; front matter parsed |
| Search ranking | Question "urea split dose" ranks the urea fixture first |
| Boost | Boost label raises matching source above an otherwise equal one |
| Min score | Nonsense question → no hits → NO_ANSWER text, `sources: []` |
| Prompt content | System has rule "Answer ONLY"; user part contains crop, fertilizer, dosage line and `[1]` passage |
| Language | `language="te"` → system contains "Reply in Telugu" |
| Index/config mismatch | Index built with dims 768, config 3072 → load refuses with a clear log |

### `test_report.py`

| Test | Assert |
| --- | --- |
| PDF download | 200, `application/pdf`, body starts with `%PDF` |
| Not owner | 404 |
| Missing fonts | Still 200; PDF text contains the English-only note |

## 14.4 Running tests

```bash
pytest -q                                   # all
pytest tests/test_dosage.py -q              # one file
pytest -k "fallback" -q                     # by name
pytest --cov=services --cov-report=term-missing   # needs pytest-cov
```

## 14.5 Manual QA checklist

**Auth**
- [ ] Register → lands on dashboard with name shown
- [ ] Logout → protected pages redirect to login; login returns to the original page

**Predictor**
- [ ] Crop dropdown has 11 crops, "Paddy (Rice)" label, no "Rice"
- [ ] "Fill sample values" fills in-range values (no amber warnings)
- [ ] N = 80 → amber border and warning on result
- [ ] Get weather for "Guntur" → temperature and humidity filled; status line shows time
- [ ] Get weather for a nonsense name → friendly message; manual entry works
- [ ] Ratings section collapses/expands; area accepts acres and hectares

**Result**
- [ ] Fertilizer, confidence badge, top-3 shown
- [ ] Dosage table and total match the worked example for Wheat/2 acres/Medium/DAP
- [ ] Schedule shows basal and top dressing quantities
- [ ] Chat: each suggested chip returns an answer with source badges in < 8 s
- [ ] Chat in Telugu, Tamil and Hindi: answer in that script; fertilizer names and numbers in English digits
- [ ] Off-topic question → polite refusal
- [ ] With an invalid API key → amber fallback bubble with passages
- [ ] Reload result page → previous chat messages shown

**History / PDF**
- [ ] History lists newest first, pagination works, View opens the saved result
- [ ] PDF downloads; tables readable; Telugu text renders when fonts are installed
- [ ] Clear history → empty state

**General**
- [ ] Mobile width (DevTools 375 px): no horizontal page scroll; chat below cards
- [ ] Keyboard only: can fill the form and send a chat message
- [ ] No console errors in the browser DevTools
- [ ] About page model card shows real CV accuracy and limitations

## 14.6 Demo script (≈ 7 minutes)

| Step | Action | Say |
| --- | --- | --- |
| 1 | Home page | "v1 predicted a fertilizer name and couldn't run from the repo. v2 fixes that and turns it into an advisor." |
| 2 | Log in as demo user | "Accounts so each farmer's history is private." |
| 3 | Predictor: type "Guntur", Get weather | "Weather fills from Open-Meteo; no key needed." |
| 4 | Fill sample values; Wheat; Loamy; 2 acres; Submit | "Inputs are validated server-side; values outside training range are flagged." |
| 5 | Result: fertilizer + confidence | "Random forest pipeline; 96% cross-validated on the public dataset — and the About page explains its limits." |
| 6 | Dosage table | "Rule-based: crop requirement, soil-test rating, then DAP/MOP/urea balancing — DAP 105.6 kg, MOP 54 kg, urea 170 kg, about ₹5,700." |
| 7 | Chat: "Why this fertilizer?" | "RAG: question embedded with Gemini, top passages from our curated knowledge base via FAISS, Gemini answers only from those — note the sources." |
| 8 | Switch to Telugu: "When do I apply urea?" | "Multilingual retrieval and answers." |
| 9 | Ask "Who won the match?" | "Guardrails keep it on topic." |
| 10 | Download PDF | "Takeaway report for the farmer." |
| 11 | History | "Everything saved in SQLite." |
| 12 | (If asked) architecture slide / docs | "15 design docs, tests offline, fallback if the AI service fails." |

Prepared answers for likely review questions:

- *Does RAG improve accuracy?* No. The classifier decides the fertilizer; RAG explains and guides using vetted content.
- *Why not let the LLM decide the dose?* Doses must be deterministic and auditable; the LLM only explains the computed numbers.
- *Dataset limits?* 99 rows, NPK on a dataset scale, weak environmental signal; next step is real Soil Health Card data.
- *What if Gemini is down?* Retrieval-only fallback, shown live if needed.

## 14.7 RAG evaluation (optional, live)

`tests/rag_eval.py` (marked `@pytest.mark.live`, skipped by default) runs the questions in Feature Development §10.4.8 against the real index and Gemini, and prints for each: top sources and scores, whether the expected source is in the top 4, answer length, citations present, latency. Run: `pytest -m live -s tests/rag_eval.py`. Target: expected source hit rate ≥ 5/6; all answers cite at least one passage; refusal for the off-topic question.

## 14.8 Defect reporting template

```text
Title: <short>
Phase / feature:
Steps to reproduce:
Expected:
Actual (exact error / screenshot):
Logs (last 20 lines):
Environment: OS, Python version, browser
```
