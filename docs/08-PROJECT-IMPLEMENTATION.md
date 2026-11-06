# 8. Project Implementation Plan

The build plan for tonight: phases, time boxes, cut lines, and a ready-to-paste Antigravity prompt for each phase. Work top to bottom; each phase ends with green tests and a git commit, so you can stop at any phase and still demo a working app.

---

## 8.1 Timeline at a glance (≈ 6 hours)

| Phase | Scope | Time box | Priority | Demo value if you stop here |
| --- | --- | --- | --- | --- |
| 0 | Repo setup, docs, AGENTS.md, venv | 20 min | P0 | — |
| 1 | Restructure (factory, blueprints, config) + core fixes + new ML pipeline | 60 min | P0 | Working v1 without bugs |
| 2 | SQLite + auth + history | 50 min | P0 | Accounts, saved history |
| 3 | RAG: knowledge base, index, chat API, chat UI | 90 min | P0 | Headline AI feature |
| 4 | Dosage & cost + schedule | 40 min | P1 | Actionable advice |
| 5 | Multilingual answers | 15 min | P1 | Telugu/Tamil/Hindi |
| 6 | Weather auto-fill | 30 min | P1 | Smoother form |
| 7 | PDF report | 30 min | P1 | Takeaway artefact |
| 8 | Polish, About/model card, tests, demo rehearsal | 35 min | P0 | Confidence in review |

**Cut lines.** If you are behind at the end of Phase 3, skip to Phase 8. Phases 4–7 are independent; do them in the order above, and drop the last ones first.

## 8.2 Milestones and checks

| Milestone | Check |
| --- | --- |
| M1 after Phase 1 | `pytest -q` green; every page route returns 200/302; Paddy prediction works |
| M2 after Phase 2 | Register → login → predict → history shows the row → logout |
| M3 after Phase 3 | Ask "Why this fertilizer?" → answer with sources in < 8 s; unplug network → fallback passages |
| M4 after Phase 7 | Full demo script in Testing & QA §14.6 passes |

## 8.3 Git workflow

```bash
git checkout -b v2-advisor
# after each phase:
pytest -q && git add -A && git commit -m "feat: phase N - <summary>"
```

Tag the demo build: `git tag demo-2026-11-07`. If a phase goes wrong: `git reset --hard HEAD` returns to the last green phase.

## 8.4 How to use the prompts in Antigravity

1. Open the repo folder in Antigravity. Put the 15 docs in `docs/`, `AGENTS.md` and `README.md` at the root, and `knowledge_base/` at the root.
2. Start a new agent conversation per phase (keeps context focused).
3. Paste the phase prompt. Review the plan the agent proposes before letting it edit files.
4. When it finishes, run the "Verify" commands yourself, check the page in the browser, then commit.
5. If something breaks, use the Debugging doc prompt (§15.8) with the exact error.

---

## 8.5 Phase prompts

### Phase 0 — Setup (do manually, 20 min)

```text
1. Fork/clone vivekg189/Fertilizer-prediction; create branch v2-advisor.
2. Copy docs/ (01–15), AGENTS.md and README.md to the repo root, knowledge_base/ to the root.
3. Create ml/data/ and put "Fertilizer Prediction.csv" there (Hugging Face mirror: kaifahmad/Fertilizer-Prediction).
4. python -m venv .venv ; activate ; pip install --upgrade pip
5. Get a Gemini API key from Google AI Studio.
```

### Phase 1 — Restructure, core fixes, ML pipeline (60 min)

```text
Read AGENTS.md, docs/03-ARCHITECTURE.md (§3.3, §3.4, §3.6, §3.8) and docs/01-PRD.md Epic A.

Restructure the existing Flask app without changing its look:
1. Create config.py (BaseConfig/DevConfig/TestConfig reading .env via python-dotenv), extensions.py
   (db, login_manager, csrf, limiter — initialise even if unused yet), app_factory.py with create_app(),
   and blueprints/core.py holding the existing routes. app.py becomes: app = create_app().
2. SECRET_KEY from env (fail fast if missing and not debug); FLASK_DEBUG default 0; remove app.run(debug=True).
3. Write ml/train.py exactly as ARCHITECTURE §3.6: strip column names, rename Temparature->Temperature,
   Pipeline(ColumnTransformer(passthrough numeric, OneHotEncoder(handle_unknown="ignore") for Soil Type/Crop Type),
   RandomForestClassifier(n_estimators=300, random_state=42)), 4-fold StratifiedKFold metrics,
   save ml/artifacts/fertilizer_pipeline.joblib and model_meta.json with the fields shown in §3.6.
4. Write services/ml_service.py: load artifacts from project-root-relative paths, options(), predict() returning
   fertilizer, confidence, top3, ood_fields, model_version. Build a one-row DataFrame with training column names.
5. Predictor dropdowns come from ml_service.options(); show "Paddy (Rice)" label for Paddy.
6. Add templates history.html (temporary: "coming soon" card) and contact.html (form per DESIGN §2.4.8, saving
   comes in Phase 2), errors/404.html, errors/500.html, and register error handlers.
7. Server-side validation with Flask-WTF PredictForm (ranges per API §5.2); friendly messages, no raw exceptions.
8. Result page shows confidence badge, top-3 and an amber out-of-range alert.
9. Fix the sample-values button to in-range values (DESIGN §2.4.4). Apply the CSS fixes in DESIGN §2.2.
10. Fix .gitignore per DATABASE §4.1. Write requirements.txt (pinned) per SETUP §9.3.
11. Tests: tests/conftest.py (app fixture with TestConfig), test_ml.py (Paddy predicts, unknown crop rejected,
    ood detection), test_smoke.py (all current routes return documented codes).

Verify: python ml/train.py && pytest -q && flask --app app run, then predict for Paddy.
```

### Phase 2 — Database, authentication, history (50 min)

```text
Read AGENTS.md, docs/04-DATABASE.md, docs/11-AUTHENTICATION-SECURITY.md, docs/05-API.md §5.2, docs/01-PRD.md Epic B.

1. Implement models.py exactly as DATABASE §4.3/§4.4 (User, Prediction, ChatMessage, ContactMessage), with the
   SQLite foreign-key pragma. Add CLI commands init-db and seed-demo (§4.6).
2. blueprints/auth.py: /register, /login, /logout (POST) with Flask-WTF forms, Werkzeug password hashing,
   safe `next` redirects, rate limits (login 5/min, register 3/min), session protection "strong".
3. Protect dashboard, predictor, predict, result, history, report and all /api routes with @login_required.
4. Change POST /predict to Post/Redirect/Get: save Prediction (user_id, inputs, outputs, model_version) and
   redirect to /result/<id>. Add get_owned_prediction_or_404 helper.
5. history.html: paginated table (10/page) per DESIGN §2.4.6 with View links; POST /history/clear with a confirm modal.
6. Dashboard: stats tiles + last 5 predictions per DESIGN §2.4.3. Contact form saves ContactMessage.
7. Navbar shows Login/Register or "Hi, <name>" + Logout per DESIGN §2.3. Add <meta name="csrf-token">.
8. Tests: test_auth.py (register, duplicate email, login fail message, logout, protected redirects),
   ownership test (user B gets 404 on user A's result), history clear.

Verify: pytest -q; register → predict → history → logout → /history redirects to login.
```

### Phase 3 — RAG chat (90 min)

```text
Read AGENTS.md, docs/03-ARCHITECTURE.md §3.5.2 and §3.7, docs/10-FEATURE-DEVELOPMENT.md §10.4,
docs/13-INTEGRATIONS.md §13.2, docs/05-API.md §5.3.1–5.3.2, docs/02-DESIGN.md §2.4.5 (chat panel).

1. services/llm_client.py using the google-genai SDK: Client from GEMINI_API_KEY; generate(prompt, system, timeout)
   with model GEMINI_MODEL (default gemini-flash-latest), temperature 0.2; embed(texts, task_type, dims=768) with
   gemini-embedding-001 in batches of up to 100; one retry with backoff on 429/5xx; raise LLMError on failure.
2. rag/build_index.py per §3.7: read knowledge_base/**/*.md except files starting with "_", parse front matter,
   split by "##" headings then ~800-char chunks with 150 overlap, prefix "title — heading", embed with
   RETRIEVAL_DOCUMENT, L2-normalise, faiss.IndexFlatIP, write faiss.index, vectors.npy (NumPy fallback), chunks.json
   (include applies_to per chunk), index_meta.json. Add a --dry-run flag that prints chunk counts/sizes without calling Gemini.
   Expected: about 34 documents and ~200 chunks.
3. services/rag_service.py: load index (NumPy cosine fallback if faiss import fails); search(question, k);
   source boost +0.05 for files matching predicted fertilizer/crop; answer() building the prompt from
   FEATURE-DEVELOPMENT §10.4 verbatim; min score threshold; no-hit message; fallback on LLMError/timeout.
4. blueprints/api.py: POST /api/chat and GET /api/chat/<prediction_id> exactly per API §5.3.1–5.3.2;
   rate limit 10/min/user; save ChatMessage rows (user + assistant with sources_json, fallback, latency_ms, model).
5. templates/partials/_chat.html + static/js/chat.js per DESIGN §2.4.5: bubbles, suggested question chips,
   typing indicator, sources badges, fallback styling, Enter to send, 500-char counter, CSRF header.
   Load saved messages when the result page opens.
6. /health reports rag_index_loaded, rag_chunks, llm_configured.
7. Tests (offline, mock llm_client): test_rag.py — chunking, search ranking with fake embeddings, fallback path,
   no-hit path, prompt contains prediction context and passages; test_api.py — chat validation, ownership, rate limit.

Verify: python rag/build_index.py; pytest -q; ask "Why this fertilizer?" on a result page; then set an invalid
GEMINI_API_KEY and confirm the fallback bubble appears.
```

### Phase 4 — Dosage & cost (40 min)

```text
Read docs/10-FEATURE-DEVELOPMENT.md §10.3, docs/04-DATABASE.md §4.7.1–4.7.2, docs/02-DESIGN.md §2.4.5, PRD Epic C.

1. data/fertilizer_products.json and data/crop_requirements.json are provided ready-made in the docs pack (values match
   DATABASE §4.7.2, FEATURE-DEVELOPMENT §10.3.6 and knowledge_base/crops/*.md). Load them; do not retype values.
2. services/dosage_service.py implementing the algorithm in §10.3 step by step (rating factors, primary product,
   DAP/Urea/MOP balancing, surplus notes, area conversion, bags, cost, schedule).
3. Add area_value, area_unit and rating_n/p/k to PredictForm and the predictor (collapsible ratings section).
4. Save dosage_json, total_cost, price_as_of on Prediction. Render partials/_dosage.html and the schedule card.
5. Pass dosage lines into the chat prompt context.
6. Tests: test_dosage.py with the worked example (Wheat, 2 acres, Medium → DAP 105.6 kg, Urea 169.8 kg,
   MOP 54.0 kg, total ₹5,702 ± 1), Urea-predicted case, Low/High ratings, hectares unit, complex product case.

Verify: pytest -q; predict Wheat 2 acres and compare with the worked example.
```

### Phase 5 — Multilingual answers (15 min)

```text
Read docs/10-FEATURE-DEVELOPMENT.md §10.5 and PRD D4.
1. Language select in the chat header (en/te/ta/hi), default current_user.preferred_language; send with each message.
2. rag_service adds the language instruction from §10.5 to the prompt; no-hit and fallback notices localised from
   the LANG_MESSAGES table in §10.5.
3. Profile: preferred_language chosen at register; add a small "Language" select on the dashboard to change it.
4. Tests: prompt contains "Reply in Telugu" when language=te; invalid language → 400.
Verify: ask the same question in Telugu and Hindi.
```

### Phase 6 — Weather auto-fill (30 min)

```text
Read docs/13-INTEGRATIONS.md §13.3, docs/05-API.md §5.3.3, docs/02-DESIGN.md §2.4.4 (Location & weather).
1. services/weather_service.py: geocode(name, count=5, language="en") and current(lat, lon) using Open-Meteo,
   timeout WEATHER_TIMEOUT_S, 10-minute in-memory cache, WeatherError on failures.
2. GET /api/weather per API §5.3.3 (single, multiple matches, not found, upstream error), rate limit 30/min.
3. static/js/weather.js: "Get weather" button, status line, match picker, fills temperature/humidity, sets
   hidden weather_source=open-meteo; manual edits switch it back to manual.
4. Tests with mocked HTTP (pytest-mock): single match, multiple matches, not found, timeout.
Verify: type "Guntur" and click Get weather.
```

### Phase 7 — PDF report (30 min)

```text
Read docs/10-FEATURE-DEVELOPMENT.md §10.6, docs/02-DESIGN.md §2.5, docs/05-API.md (/report/<id>.pdf).
1. services/report_service.py with fpdf2: layout per DESIGN §2.5; register Noto Sans fonts from PDF_FONT_DIR when
   present (NotoSans, NotoSansTelugu, NotoSansTamil, NotoSansDevanagari) and use the matching font per chat
   message language; if fonts are missing, include only English messages and add a note.
2. Route GET /report/<id>.pdf (owner only) returning send_file(BytesIO, mimetype application/pdf, download_name).
3. "Download PDF" buttons on result and history.
4. Tests: response is 200, content-type PDF, starts with %PDF; other user gets 404.
Verify: download a report for a prediction with chat in English and Telugu.
```

### Phase 8 — Polish and demo readiness (35 min)

```text
Read docs/14-TESTING-QA.md and docs/02-DESIGN.md §2.4.1 and §2.4.7.
1. About page model card from model_meta.json and the Limitations section; Home stats from meta (no hard-coded 95%).
2. Run the full manual checklist in TESTING-QA §14.5; fix anything failing.
3. Make sure pytest -q is green and there are no print() calls or debug flags.
4. Update README if anything changed. Seed the demo user and 2 sample predictions.
Verify: run the demo script in TESTING-QA §14.6 twice from a fresh DB.
```

## 8.6 Effort tracking

| Phase | Planned | Actual | Notes |
| --- | --- | --- | --- |
| 0 | 20 m | | |
| 1 | 60 m | | |
| 2 | 50 m | | |
| 3 | 90 m | | |
| 4 | 40 m | | |
| 5 | 15 m | | |
| 6 | 30 m | | |
| 7 | 30 m | | |
| 8 | 35 m | | |

## 8.7 Post-demo backlog

1. Larger, real soil-test dataset; retrain and recalibrate.
2. Flask-Migrate for schema changes.
3. Deployment (Render/Railway/OCI) with gunicorn and a persistent volume for SQLite.
4. Crop recommendation model; disease detection from leaf images.
5. Admin view for contact messages and knowledge-base reviews.
6. Evaluation set for RAG answers (question → expected sources) run in CI.
