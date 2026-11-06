# 1. Product Requirements Document (PRD)

**Product:** Smart Fertilizer Advisor (v2 of `vivekg189/Fertilizer-prediction`)
**Status:** Approved for build · **Target:** Project review demo
**Owner:** Project team · **Last updated:** 2026-11-06

---

## 1.1 Summary

Smart Fertilizer Advisor turns the existing "predict a fertilizer name" Flask app into a farm advisory tool. A logged-in farmer enters soil, crop and weather details and receives:

1. The recommended fertilizer (ML classifier), with a confidence score and an out-of-range warning.
2. How much to apply (kg per acre/ha and number of bags) and what it costs.
3. A chat assistant that explains the recommendation, grounded in a curated agronomy knowledge base (RAG), in English, Telugu, Tamil or Hindi.
4. A downloadable PDF report of the recommendation, dosage, cost and chat answers.

Temperature and humidity can be auto-filled from a city or village name.

## 1.2 Problem statement

The v1 app has these problems (from the code review):

| # | v1 problem | Impact |
| --- | --- | --- |
| P1 | Model and dataset never committed (`.gitignore` excludes `*.pkl`, `*.csv`) | App cannot predict out of the box |
| P2 | `/history` and `/contact` return HTTP 500 (templates missing) | Broken navigation |
| P3 | "Rice" in the crop list does not exist in the data ("Paddy") | Error on every Rice prediction |
| P4 | Only a fertilizer name; no quantity, cost, reason or confidence | Not actionable for a farmer |
| P5 | History kept in a cookie with a random secret key | Lost on restart; unbounded growth |
| P6 | `debug=True`, no auth, raw exception text shown to users | Not safe to demo on a network |
| P7 | Hard-coded "95% accuracy" and README claims not backed by code | Credibility risk in review |

## 1.3 Goals and non-goals

**Goals**

- G1. Every route works; no HTTP 500 in the demo path.
- G2. Each prediction shows fertilizer, confidence, and a warning when inputs are outside the training range.
- G3. Dosage and cost for the farm area, using editable crop requirements and fertilizer prices.
- G4. RAG chat that answers questions about the recommendation, cites knowledge-base sources, and replies in the chosen language.
- G5. User accounts with saved predictions and chat history (SQLite).
- G6. PDF report download per prediction.
- G7. Weather auto-fill (temperature, humidity) from a place name.
- G8. Honest metrics: accuracy shown in the UI comes from `model_meta.json`, produced by the training script.

**Non-goals (out of scope for this release)**

- Retraining on a new, larger dataset (documented as future work).
- Image-based disease detection, mobile app, SMS/WhatsApp bot.
- Payment, marketplace, or real fertilizer ordering.
- Admin portal (an admin can inspect SQLite directly).
- Production cloud deployment (local demo only; deployment notes in Setup).

## 1.4 Users and personas

| Persona | Description | Primary need |
| --- | --- | --- |
| Farmer (primary) | Small/medium landholder, 1–10 acres, may prefer Telugu/Tamil/Hindi | "What do I apply, how much, what will it cost, when?" |
| Agri student / extension worker | Helps farmers, comfortable in English | Explanation and sources behind the advice |
| Reviewer / evaluator | Judges the project in the demo | Working flow, clear architecture, honest limitations |

## 1.5 User stories and acceptance criteria

### Epic A — Core prediction (fix v1)

| ID | Story | Acceptance criteria |
| --- | --- | --- |
| A1 | As a farmer, I can pick any crop the model knows | Crop and soil dropdowns are built from the model's label encoders: 11 crops, 5 soils. "Paddy" shown as "Paddy (Rice)". No crop in the list can fail encoding |
| A2 | As a farmer, I get a recommendation with confidence | Result shows fertilizer name and top-class probability as a percentage, plus the top-3 alternatives |
| A3 | As a farmer, I'm warned when my values are unusual | Any input outside the training min–max shows an amber warning listing the fields; prediction still shown |
| A4 | Invalid inputs give clear messages | Field-level messages ("Nitrogen must be a whole number 0–255"); never raw Python exception text |
| A5 | All nav links work | `/history`, `/contact` render; no route returns 500 in the smoke test |

### Epic B — Accounts and history

| ID | Story | Acceptance criteria |
| --- | --- | --- |
| B1 | I can register and log in | Register with name, email, password (min 8 chars); login/logout; passwords hashed |
| B2 | Predictor, results, chat, history and reports need login | Anonymous users are redirected to login with a `next` parameter |
| B3 | My predictions are saved | Each prediction is stored with inputs, outputs, dosage and cost; History page lists newest first, paginated 10 per page |
| B4 | I can reopen a past result | Clicking a history row opens its result page including saved chat |
| B5 | I can delete my history | "Clear history" deletes only the current user's predictions and chats after a confirm dialog |
| B6 | Dashboard shows my recent activity | Last 5 predictions and counts (total predictions, chats) |

### Epic C — Dosage and cost

| ID | Story | Acceptance criteria |
| --- | --- | --- |
| C1 | I can enter farm area | Area field with unit (acres default, or hectares); 0.1–1000 |
| C2 | I can set soil test ratings | Optional Low/Medium/High for N, P, K (default Medium), as on a Soil Health Card |
| C3 | I see quantities | Per product: kg/ha, kg for my area, bags (rounded up), based on the algorithm in Feature Development §10.3 |
| C4 | I see cost | Cost per product and total in ₹, using `data/fertilizer_products.json`; label "approximate, based on configured MRP" |
| C5 | I see when to apply | Split schedule (basal / top dress) per crop from `data/crop_requirements.json` |

### Epic D — RAG chat assistant

| ID | Story | Acceptance criteria |
| --- | --- | --- |
| D1 | I can ask questions on the result page | Chat panel with input, send button and 4 suggested questions |
| D2 | Answers use my prediction | The prompt includes crop, soil, NPK, fertilizer, confidence and dosage |
| D3 | Answers are grounded | Each answer lists 1–4 source documents; if no relevant chunk passes the similarity threshold, the bot says it does not know and suggests a local agriculture officer |
| D4 | I can choose a language | Language selector: English, తెలుగు, தமிழ், हिन्दी; the answer comes in that language |
| D5 | It degrades gracefully | If Gemini fails or times out (15 s), show the top retrieved passages with a notice instead of an error |
| D6 | Chat is saved | Messages are stored against the prediction and shown when it is reopened |
| D7 | It stays on topic | Off-topic or unsafe questions get a polite refusal; no medical/pesticide-dose advice beyond the knowledge base |

### Epic E — Weather auto-fill

| ID | Story | Acceptance criteria |
| --- | --- | --- |
| E1 | I can fill weather from a place name | "Get weather" button next to a location field; fills temperature (°C) and humidity (%) from Open-Meteo |
| E2 | Ambiguous names are handled | If several matches, show up to 5 (name, district/state) to choose from |
| E3 | Failures don't block | On error or no network, show "Weather unavailable, enter manually"; fields stay editable |

### Epic F — PDF report

| ID | Story | Acceptance criteria |
| --- | --- | --- |
| F1 | I can download a report | "Download PDF" on the result page and on history rows |
| F2 | Report contents | Farmer name, date, location, inputs table, recommendation + confidence, warnings, dosage and cost table, application schedule, last 5 chat Q&As, disclaimer |
| F3 | Regional language text renders | Telugu/Tamil/Hindi chat text renders correctly when Noto fonts are installed; otherwise English-only report with a note |

## 1.6 Functional scope by priority

| Priority | Scope | Rationale |
| --- | --- | --- |
| P0 (must, demo blocker) | Epic A, B1–B3, D1–D5 | Working core + the headline AI feature |
| P1 (should) | C1–C5, F1–F2, E1–E3, B4–B6, D6–D7 | High demo value, moderate effort |
| P2 (could) | F3 regional fonts in PDF, B5, pagination polish | Nice to have |

If time runs out, ship P0 and P1 in that order; P2 can be described in the review as next steps.

## 1.7 Non-functional requirements

| Area | Requirement |
| --- | --- |
| Performance | Prediction < 300 ms server time; chat answer < 8 s p95 (Gemini); PDF < 2 s |
| Availability | Demo runs locally; chat falls back to retrieved passages if Gemini is unavailable |
| Security | Password hashing, CSRF on all forms and JSON POSTs, login required for user data, secrets in `.env`, debug off by default, per-user data isolation |
| Privacy | Store only name, email, farm inputs, chats; no phone/Aadhaar; location stored only as the typed place name |
| Accessibility | Labels on all inputs, keyboard-usable chat, colour not the only signal for warnings |
| Localisation | UI chrome in English; chat answers in 4 languages |
| Maintainability | App factory + blueprints + services; crop requirements and prices in JSON, not code |
| Testability | pytest suite runs offline (LLM and weather mocked) in < 30 s |

## 1.8 Success metrics (demo)

- Full demo script (Testing & QA §14.6) runs end to end with zero errors.
- 4 prepared chat questions answered with sources in under 8 s each.
- Smoke test: every route returns 200/302 as specified.
- Model card on the About page shows the real cross-validated accuracy from `model_meta.json`.

## 1.9 Constraints and assumptions

- Python 3.10+; runs on Windows, macOS or Linux laptop.
- Internet needed for Gemini and Open-Meteo during the demo; a free Gemini API key from Google AI Studio.
- The ML dataset is the public 99-row "Fertilizer Prediction" CSV. Its N/P/K values are not real soil-test kg/ha figures; this limitation is stated on the About page and in the knowledge base.
- Crop nutrient requirements and fertilizer prices are typical values for India and must be verified before relying on them; they are labelled "approximate" in the UI.

## 1.10 Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| No internet / Gemini quota at demo | Medium | High | Retrieval-only fallback; mobile hotspot; pre-warm with a test question |
| Knowledge base contains a wrong fact | Medium | Medium | Verification checklist in `knowledge_base/_INDEX.md`; "educational" label |
| Scope too large for one night | High | High | Priority tiers above; Project Implementation has time boxes and cut lines |
| Reviewer asks about model accuracy | High | Medium | Show model card; explain dataset limits and that RAG explains but does not change predictions |
| Windows install issues (faiss) | Low | Medium | NumPy cosine-similarity fallback in `rag_service` |

## 1.11 Glossary

- **RAG** — Retrieval-Augmented Generation: retrieve relevant knowledge-base passages, then ask the LLM to answer using only them.
- **Chunk** — a ~800-character slice of a knowledge-base document, embedded as one vector.
- **N, P, K** — nitrogen, phosphorus (as P₂O₅ in fertilizer grades), potassium (as K₂O).
- **RD** — recommended dose of N-P₂O₅-K₂O in kg/ha for a crop.
- **Basal / top dressing** — fertilizer applied at sowing / later in the season.
- **OOD** — out of distribution: an input outside the range the model was trained on.
