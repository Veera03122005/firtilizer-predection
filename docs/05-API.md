# 5. API Reference

All HTTP endpoints of Smart Fertilizer Advisor: page routes (HTML) and JSON APIs. Base URL in development: `http://127.0.0.1:5000`.

---

## 5.1 Conventions

| Topic | Rule |
| --- | --- |
| Auth | Session cookie (Flask-Login). Endpoints marked 🔒 require login; anonymous page requests redirect to `/login?next=…`, anonymous JSON requests get `401`. |
| CSRF | Every `POST` needs a CSRF token: hidden `csrf_token` field in forms, `X-CSRFToken` header for JSON (read from `<meta name="csrf-token">`). Missing/invalid → `400`. |
| Content type | JSON APIs accept and return `application/json; charset=utf-8`. |
| Ownership | A prediction or chat belonging to another user returns `404` (not `403`), to avoid revealing IDs. |
| Errors (JSON) | `{"error": {"code": "<SNAKE_CASE>", "message": "<human readable>", "fields": {...optional}}}` |
| Rate limits | Login 5/min/IP; register 3/min/IP; chat 10/min/user; weather 30/min/user; exceeded → `429` with `Retry-After`. |
| Time | ISO 8601 UTC in JSON (`2026-11-06T12:30:00Z`); pages display IST. |

### Error codes

| HTTP | `code` | When |
| --- | --- | --- |
| 400 | `VALIDATION_ERROR` | Invalid fields (`fields` lists them) |
| 400 | `CSRF_FAILED` | Missing/invalid CSRF token |
| 401 | `AUTH_REQUIRED` | Not logged in |
| 404 | `NOT_FOUND` | Missing or not owned |
| 429 | `RATE_LIMITED` | Too many requests |
| 502 | `UPSTREAM_ERROR` | Open-Meteo failed (chat never returns this; it falls back) |
| 503 | `MODEL_UNAVAILABLE` | ML artifact not loaded |
| 500 | `INTERNAL_ERROR` | Unexpected; details only in server log |

## 5.2 Page routes (HTML)

| Method | Path | Auth | Purpose | Responses |
| --- | --- | --- | --- | --- |
| GET | `/` | – | Home | 200 |
| GET | `/about` | – | About + model card | 200 |
| GET, POST | `/contact` | – | Contact form; POST saves message | 200; POST → 302 `/contact` with flash |
| GET, POST | `/register` | – | Create account | 200; POST success → 302 `/dashboard`; errors → 200 with field errors |
| GET, POST | `/login` | – | Log in | 200; success → 302 to safe `next` or `/dashboard`; failure → 200 + flash |
| POST | `/logout` | 🔒 | Log out (POST + CSRF, not GET) | 302 `/` |
| GET | `/dashboard` | 🔒 | Stats + recent predictions | 200 |
| GET | `/predictor` | 🔒 | Prediction form | 200; model missing → 200 with banner, submit disabled |
| POST | `/predict` | 🔒 | Validate, predict, compute dosage, save | 302 `/result/<id>`; validation errors → 400 re-render form; model missing → 503 page |
| GET | `/result/<int:id>` | 🔒 | Result, dosage, schedule, chat | 200; 404 |
| GET | `/history?page=N` | 🔒 | Paginated history (10/page) | 200 |
| POST | `/history/clear` | 🔒 | Delete all of the user's predictions + chats | 302 `/history` |
| GET | `/report/<int:id>.pdf` | 🔒 | PDF report | 200 `application/pdf` (`Content-Disposition: attachment; filename="fertilizer-report-<id>.pdf"`); 404 |
| GET | `/health` | – | Liveness + component status (JSON) | 200 / 503 |

`next` redirect safety: only relative paths starting with `/` and not `//` are accepted.

### `POST /predict` form fields

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `location` | string | No | ≤ 120 chars |
| `weather_source` | `open-meteo` \| `manual` | No | Default `manual` |
| `temperature` | float | Yes | 0–50 |
| `humidity` | float | Yes | 0–100 |
| `moisture` | float | Yes | 0–100 |
| `soil` | string | Yes | In `model_meta.soil_types` |
| `crop` | string | Yes | In `model_meta.crop_types` |
| `nitrogen`, `phosphorous`, `potassium` | int | Yes | 0–255 |
| `rating_n`, `rating_p`, `rating_k` | `Low`\|`Medium`\|`High` | No | Default `Medium` |
| `area_value` | float | Yes | 0.1–1000 |
| `area_unit` | `acre` \| `ha` | Yes | Default `acre` |
| `csrf_token` | string | Yes | |

Values outside the model's training range are accepted but flagged (`ood_fields`).

### `GET /health`

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_version": "2026.11.06-rf300",
  "rag_index_loaded": true,
  "rag_chunks": 214,
  "llm_configured": true,
  "db": "ok"
}
```

`status` is `"degraded"` (HTTP 200) when only the LLM key is missing, and `"error"` (HTTP 503) when the model or DB is unavailable.

## 5.3 JSON APIs

### 5.3.1 `POST /api/chat` 🔒

Ask the RAG assistant about a prediction.

**Request**

```json
{
  "prediction_id": 42,
  "question": "When should I apply the second dose of urea?",
  "language": "te"
}
```

| Field | Rule |
| --- | --- |
| `prediction_id` | int, must belong to the user |
| `question` | string, 1–500 chars after trim |
| `language` | `en` \| `te` \| `ta` \| `hi`; default user's preferred language |

**Response 200**

```json
{
  "message_id": 318,
  "answer": "గోధుమలో యూరియా రెండవ మోతాదును మొదటి నీటి తడి సమయంలో (విత్తిన 20–25 రోజులకు) వేయండి... [1]",
  "language": "te",
  "sources": [
    {"n": 1, "source": "crops/wheat.md", "title": "Wheat", "heading": "Fertilizer schedule", "score": 0.78},
    {"n": 2, "source": "fertilizers/urea.md", "title": "Urea (46-0-0)", "heading": "How to apply", "score": 0.71}
  ],
  "fallback": false,
  "latency_ms": 3120
}
```

**Response 200 — fallback (LLM unavailable)**

```json
{
  "message_id": 319,
  "answer": "The AI service is unavailable right now. Most relevant passages:\n\n[1] Wheat — Fertilizer schedule: Apply half the nitrogen ...",
  "language": "en",
  "sources": [{"n": 1, "source": "crops/wheat.md", "title": "Wheat", "heading": "Fertilizer schedule", "score": 0.78}],
  "fallback": true,
  "latency_ms": 15040
}
```

**Response 200 — no relevant knowledge**

```json
{"message_id": 320, "answer": "I don't have reliable information on that in my knowledge base. Please check with your local agriculture officer or Krishi Vigyan Kendra.", "language": "en", "sources": [], "fallback": false, "latency_ms": 420}
```

Errors: 400 `VALIDATION_ERROR`, 401, 404, 429.

### 5.3.2 `GET /api/chat/<int:prediction_id>` 🔒

Chat history for one prediction, oldest first.

```json
{
  "prediction_id": 42,
  "messages": [
    {"id": 317, "role": "user", "content": "Why DAP?", "language": "en", "created_at": "2026-11-06T12:30:00Z"},
    {"id": 318, "role": "assistant", "content": "DAP supplies ...", "language": "en", "sources": [...], "fallback": false, "created_at": "2026-11-06T12:30:03Z"}
  ]
}
```

### 5.3.3 `GET /api/weather` 🔒

| Query param | Rule |
| --- | --- |
| `q` | Place name, 2–80 chars (required unless `lat`/`lon` given) |
| `lat`, `lon` | Floats; used after the user picks one of several matches |
| `name` | Display name of the chosen match (optional, echoed back) |

**Response 200 — single match / coordinates given**

```json
{
  "place": "Guntur, Andhra Pradesh, India",
  "latitude": 16.3, "longitude": 80.45,
  "temperature_c": 31.4,
  "humidity_pct": 64,
  "observed_at": "2026-11-06T08:30",
  "source": "open-meteo"
}
```

**Response 200 — several matches**

```json
{
  "matches": [
    {"name": "Guntur", "admin1": "Andhra Pradesh", "country": "India", "latitude": 16.3, "longitude": 80.45},
    {"name": "Guntur", "admin1": "...", "country": "India", "latitude": 0, "longitude": 0}
  ]
}
```

Errors: 400 `VALIDATION_ERROR`; 404 `NOT_FOUND` ("No place found"); 502 `UPSTREAM_ERROR`; 429.

### 5.3.4 `POST /api/predict` 🔒

JSON version of the predictor, for testing and integrations. Same fields as the form (§5.2) minus `csrf_token` (CSRF header still required for browser sessions). Saves the prediction like the form does.

**Response 201**

```json
{
  "prediction_id": 43,
  "fertilizer": "DAP",
  "confidence": 0.82,
  "top3": [{"label": "DAP", "p": 0.82}, {"label": "14-35-14", "p": 0.09}, {"label": "28-28", "p": 0.05}],
  "ood_fields": [],
  "model_version": "2026.11.06-rf300",
  "dosage": {
    "area_ha": 0.8094,
    "lines": [
      {"product": "DAP",  "kg_per_ha": 130.4, "kg_total": 105.6, "bags": 2.11, "bags_rounded": 3, "cost": 2850},
      {"product": "MOP",  "kg_per_ha": 66.7,  "kg_total": 54.0,  "bags": 1.08, "bags_rounded": 2, "cost": 1846},
      {"product": "Urea", "kg_per_ha": 209.8, "kg_total": 169.8, "bags": 3.77, "bags_rounded": 4, "cost": 1006}
    ],
    "total_cost": 5702,
    "price_as_of": "2026-03",
    "targets_kg_ha": {"N": 120.0, "P2O5": 60.0, "K2O": 40.0},
    "schedule": [
      {"stage": "Basal (at sowing)", "items": ["DAP: 105.6 kg", "MOP: 54.0 kg", "Urea: 64.3 kg"]},
      {"stage": "First irrigation / crown root initiation (20–25 days)", "items": ["Urea: 105.6 kg"]}
    ],
    "notes": []
  },
  "result_url": "/result/43"
}
```

(Example: Wheat, 2 acres, all ratings Medium, predicted DAP. Cost = exact kg × price per kg; see Feature Development §10.3.)

## 5.4 Example calls

```bash
# Health
curl -s http://127.0.0.1:5000/health

# Chat (inside a logged-in browser session use fetch; from a terminal, log in with a cookie jar first)
curl -s -c jar.txt -b jar.txt http://127.0.0.1:5000/login   # get csrf token from the form, then POST credentials
```

```javascript
// static/js/chat.js
const token = document.querySelector('meta[name="csrf-token"]').content;
const res = await fetch('/api/chat', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'X-CSRFToken': token},
  body: JSON.stringify({prediction_id: 42, question: 'Why DAP?', language: 'en'})
});
const data = await res.json();
```

## 5.5 Versioning and compatibility

- APIs are unversioned for the demo (`/api/...`). If exposed later, move to `/api/v1/...`.
- Responses only add fields over time; clients must ignore unknown fields.
