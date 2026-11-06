# 13. Integrations

External services and libraries the app depends on, how each is called, its limits, failure modes and fallbacks.

---

## 13.1 Integration map

| Integration | Type | Used by | Key needed | Failure behaviour |
| --- | --- | --- | --- | --- |
| Google Gemini — generation | HTTPS API (`google-genai`) | `llm_client.generate` | `GEMINI_API_KEY` | Chat returns retrieved passages (`fallback: true`) |
| Google Gemini — embeddings | HTTPS API | `build_index.py`, `rag_service.search` | `GEMINI_API_KEY` | Index build fails loudly; at query time keyword fallback |
| Open-Meteo Geocoding | HTTPS API (`requests`) | `weather_service.geocode` | None | "Weather unavailable, enter manually" |
| Open-Meteo Forecast | HTTPS API | `weather_service.current` | None | Same |
| FAISS | Local library | `rag_service` | — | NumPy cosine search |
| fpdf2 (+ uharfbuzz) | Local library | `report_service` | — | English-only PDF note if Indic shaping unavailable |
| Bootstrap 5.3 + Icons | CDN (jsDelivr) | Templates | — | Unstyled but working pages offline |
| Noto fonts | Local TTF files | PDF | — | English-only regional text note |

## 13.2 Google Gemini

### 13.2.1 SDK and client

- Package: `google-genai` (`from google import genai`, `from google.genai import types`).
- The client reads `GEMINI_API_KEY` (or `GOOGLE_API_KEY`, which takes precedence if both are set). We pass it explicitly from config.

```python
# services/llm_client.py
from __future__ import annotations
import logging, time
from google import genai
from google.genai import types, errors

log = logging.getLogger(__name__)

class LLMError(Exception):
    pass

class LLMClient:
    def __init__(self, api_key: str | None, model: str, embed_model: str,
                 timeout_s: int = 15, temperature: float = 0.2):
        self.enabled = bool(api_key)
        self.model, self.embed_model, self.temperature = model, embed_model, temperature
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_s * 1000),   # milliseconds
        ) if self.enabled else None

    def _retry(self, fn):
        for attempt in (1, 2):
            try:
                return fn()
            except errors.APIError as e:
                retryable = getattr(e, "code", None) in (429, 500, 502, 503, 504)
                log.warning("Gemini API error %s (attempt %d)", getattr(e, "code", "?"), attempt)
                if attempt == 2 or not retryable:
                    raise LLMError(str(e)) from e
                time.sleep(1.5)
            except Exception as e:          # network/timeout errors from the HTTP layer
                if attempt == 2:
                    raise LLMError(str(e)) from e
                time.sleep(1.0)

    def generate(self, system: str, user: str, max_tokens: int = 600) -> str:
        if not self.enabled:
            raise LLMError("GEMINI_API_KEY not configured")
        cfg = types.GenerateContentConfig(system_instruction=system,
                                          temperature=self.temperature,
                                          max_output_tokens=max_tokens)
        resp = self._retry(lambda: self.client.models.generate_content(
            model=self.model, contents=user, config=cfg))
        text = (resp.text or "").strip()
        if not text:
            raise LLMError("Empty response (possibly blocked by safety filters)")
        return text

    def embed(self, texts: list[str], task_type: str, dims: int = 768) -> list[list[float]]:
        if not self.enabled:
            raise LLMError("GEMINI_API_KEY not configured")
        out = []
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]
            resp = self._retry(lambda: self.client.models.embed_content(
                model=self.embed_model, contents=batch,
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=dims)))
            out.extend(e.values for e in resp.embeddings)
        return out
```

### 13.2.2 Models and settings

| Purpose | Setting | Default | Notes |
| --- | --- | --- | --- |
| Generation | `GEMINI_MODEL` | `gemini-flash-latest` | Alias that tracks the current Flash model; pin a specific version ID after the demo if you need stable behaviour |
| Embeddings | `GEMINI_EMBED_MODEL` | `gemini-embedding-001` | Multilingual; `output_dimensionality=768`; normalise vectors yourself when dims < full size |
| Document embeddings | `task_type` | `RETRIEVAL_DOCUMENT` | Index build |
| Query embeddings | `task_type` | `RETRIEVAL_QUERY` | Each question |

Changing the embedding model or dimensions requires rebuilding the index (`index_meta.json` records both; `rag_service` refuses to load an index whose model/dims differ from config and logs why).

### 13.2.3 Limits and cost

- Free-tier requests-per-minute and per-day limits apply and change over time; check your key's limits in Google AI Studio.
- Index build: a few hundred chunks in batches of 100, so a handful of embedding requests.
- Each chat: 1 embedding call + 1 generation call (~2–3k input tokens, ≤ 600 output tokens).
- Protect quota with the chat rate limit (10/min/user) and the context cap.

### 13.2.4 Errors

| Error | Cause | App behaviour |
| --- | --- | --- |
| 400 `INVALID_ARGUMENT` | Bad model name or parameter | `LLMError` → fallback; log the message |
| 403 `PERMISSION_DENIED` | Invalid/revoked key, API not enabled | Fallback; `/health` shows `llm_configured: true` but logs errors — check key |
| 429 `RESOURCE_EXHAUSTED` | Quota/rate limit | One retry after 1.5 s, then fallback |
| 5xx | Service issue | One retry, then fallback |
| Timeout | Slow network | Fallback after `LLM_TIMEOUT_S` |
| Empty text | Safety block | Fallback with passages |

## 13.3 Open-Meteo (weather)

Free, no API key, for non-commercial use within fair-use limits. Attribute "Weather data by Open-Meteo.com" in the UI under the weather status line.

### 13.3.1 Geocoding

```
GET https://geocoding-api.open-meteo.com/v1/search?name=Guntur&count=5&language=en&format=json
```

Relevant response fields: `results[].name`, `admin1` (state), `country`, `latitude`, `longitude`. No `results` key = no match.

### 13.3.2 Current weather

```
GET https://api.open-meteo.com/v1/forecast?latitude=16.3&longitude=80.45&current=temperature_2m,relative_humidity_2m&timezone=auto
```

Relevant fields: `current.time`, `current.temperature_2m` (°C), `current.relative_humidity_2m` (%).

### 13.3.3 Service code

```python
# services/weather_service.py
from __future__ import annotations
import time, requests

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FC_URL = "https://api.open-meteo.com/v1/forecast"

class WeatherError(Exception):
    pass

class WeatherService:
    def __init__(self, timeout_s: int = 8, ttl_s: int = 600):
        self.timeout, self.ttl, self._cache = timeout_s, ttl_s, {}

    def _get(self, url, params):
        key = (url, tuple(sorted(params.items())))
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self.ttl:
            return hit[1]
        try:
            r = requests.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            raise WeatherError(str(e)) from e
        self._cache[key] = (time.time(), data)
        return data

    def geocode(self, name: str, count: int = 5) -> list[dict]:
        data = self._get(GEO_URL, {"name": name, "count": count, "language": "en", "format": "json"})
        return [{"name": r["name"], "admin1": r.get("admin1", ""), "country": r.get("country", ""),
                 "latitude": r["latitude"], "longitude": r["longitude"]} for r in data.get("results", [])]

    def current(self, lat: float, lon: float) -> dict:
        data = self._get(FC_URL, {"latitude": lat, "longitude": lon,
                                  "current": "temperature_2m,relative_humidity_2m", "timezone": "auto"})
        cur = data.get("current") or {}
        if "temperature_2m" not in cur:
            raise WeatherError("No current weather in response")
        return {"temperature_c": cur["temperature_2m"], "humidity_pct": cur["relative_humidity_2m"],
                "observed_at": cur.get("time")}
```

Indian village names often resolve to several places, or none; the UI lets the user pick or fall back to manual entry.

## 13.4 FAISS

- Package `faiss-cpu`. Index type `IndexFlatIP` over L2-normalised float32 vectors (inner product = cosine).
- Save/load: `faiss.write_index(index, path)`, `faiss.read_index(path)`.
- Fallback when import fails:

```python
try:
    import faiss
except ImportError:
    faiss = None
# fallback search
scores = self.matrix @ q            # matrix: (n, 768) normalised, q: (768,)
idx = np.argsort(-scores)[:k * 3]
```

For the NumPy fallback, store vectors also as `rag/index/vectors.npy` during the build.

## 13.5 fpdf2 (PDF)

- `pip install fpdf2` (import name `fpdf`). Optional `uharfbuzz` for Indic text shaping.
- Register fonts: `pdf.add_font("NotoSans", "", "static/fonts/NotoSans-Regular.ttf")`, same for Bold, Telugu, Tamil, Devanagari.
- `pdf.set_text_shaping(True)` only if `uharfbuzz` is importable.
- Output: `bytes(pdf.output())` → `send_file(BytesIO(...), mimetype="application/pdf", as_attachment=True, download_name=...)`.

## 13.6 Front-end CDNs

| Asset | Source |
| --- | --- |
| Bootstrap CSS/JS 5.3 (latest stable patch) | `https://cdn.jsdelivr.net/npm/bootstrap@5.3.x/dist/...` with SRI hashes from getbootstrap.com |
| Bootstrap Icons | `https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.x/font/bootstrap-icons.min.css` |

Replace `5.3.x` with the exact version shown on getbootstrap.com and copy its `integrity` attribute. For an offline demo, download both into `static/vendor/` and reference locally.

## 13.7 Data sources

| Data | Source | Notes |
| --- | --- | --- |
| Training CSV | Public "Fertilizer Prediction" dataset (Kaggle; mirrored on Hugging Face `kaifahmad/Fertilizer-Prediction`) | 99 rows; commit to `ml/data/` |
| Fertilizer prices | Government MRP (urea), news reports of MRP/average retail prices (DAP, MOP, 10-26-26, March 2026) | Edit `data/fertilizer_products.json`; verify with a local dealer |
| Crop RD values | General Indian recommendations (state packages of practices, ICAR guidance) | Verify per state; mirrored in the knowledge base |

## 13.8 Integration test matrix

| Scenario | How to simulate | Expected |
| --- | --- | --- |
| No Gemini key | Empty `GEMINI_API_KEY` | `/health` degraded; chat fallback |
| Invalid key | Wrong key | Chat fallback; error logged |
| Gemini timeout | `LLM_TIMEOUT_S=1` | Fallback within ~2 s |
| Offline | Disable Wi-Fi | Weather message; chat keyword fallback; predictions still work |
| FAISS missing | `pip uninstall faiss-cpu` | NumPy search, same results |
| Fonts missing | Empty `static/fonts/` | PDF with English-only note |
