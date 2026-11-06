# 10. Feature Development

Detailed behaviour, algorithms and reference code for each feature. This is the source of truth for logic; the PRD says *what*, this document says *exactly how*.

---

## 10.1 Feature index

| § | Feature | Service | PRD epic |
| --- | --- | --- | --- |
| 10.2 | Fertilizer prediction (fixed) | `ml_service` | A |
| 10.3 | Dosage, cost and schedule | `dosage_service` | C |
| 10.4 | RAG chat assistant | `rag_service`, `llm_client` | D |
| 10.5 | Multilingual answers | `rag_service` | D4 |
| 10.6 | PDF report | `report_service` | F |
| 10.7 | Weather auto-fill | `weather_service` | E |
| 10.8 | Accounts, history, dashboard | `auth`, `core` blueprints | B |

---

## 10.2 Fertilizer prediction

### Behaviour

1. Options: `ml_service.options()` returns `soil_types` and `crop_types` from `model_meta.json`.
2. Validation (server): numeric ranges per API §5.2; soil/crop must be in options.
3. Prediction: one-row DataFrame with columns `Temperature, Humidity, Moisture, Soil Type, Crop Type, Nitrogen, Potassium, Phosphorous` → `pipeline.predict_proba`.
4. Output: `fertilizer` (argmax), `confidence` (max probability), `top3` (sorted), `ood_fields`, `model_version`.

### Reference code

```python
# services/ml_service.py
from __future__ import annotations
import json, logging
from dataclasses import dataclass, field
from pathlib import Path
import joblib, pandas as pd, sklearn

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "ml" / "artifacts"
FEATURES = ["Temperature", "Humidity", "Moisture", "Soil Type", "Crop Type",
            "Nitrogen", "Potassium", "Phosphorous"]
RANGE_KEYS = {"temperature": "Temperature", "humidity": "Humidity", "moisture": "Moisture",
              "nitrogen": "Nitrogen", "potassium": "Potassium", "phosphorous": "Phosphorous"}

@dataclass
class PredictionResult:
    fertilizer: str
    confidence: float
    top3: list[dict]
    ood_fields: list[str] = field(default_factory=list)
    model_version: str = ""

class MLService:
    def __init__(self, art_dir: Path = ART):
        self.pipeline, self.meta = None, {}
        try:
            self.pipeline = joblib.load(art_dir / "fertilizer_pipeline.joblib")
            self.meta = json.loads((art_dir / "model_meta.json").read_text(encoding="utf-8"))
            if self.meta.get("sklearn_version") != sklearn.__version__:
                log.warning("Model trained with scikit-learn %s, running %s — retrain recommended",
                            self.meta.get("sklearn_version"), sklearn.__version__)
        except FileNotFoundError:
            log.error("Model artifacts missing in %s — run python ml/train.py", art_dir)

    @property
    def loaded(self) -> bool:
        return self.pipeline is not None

    def options(self) -> dict:
        return {"soil_types": self.meta.get("soil_types", []), "crop_types": self.meta.get("crop_types", [])}

    def predict(self, x: dict) -> PredictionResult:
        row = pd.DataFrame([{
            "Temperature": x["temperature"], "Humidity": x["humidity"], "Moisture": x["moisture"],
            "Soil Type": x["soil"], "Crop Type": x["crop"], "Nitrogen": x["nitrogen"],
            "Potassium": x["potassium"], "Phosphorous": x["phosphorous"]}], columns=FEATURES)
        proba = self.pipeline.predict_proba(row)[0]
        classes = list(self.pipeline.classes_)
        ranked = sorted(zip(classes, proba), key=lambda t: -t[1])
        ood = [col for key, col in RANGE_KEYS.items()
               if not (self.meta["ranges"][col][0] <= x[key] <= self.meta["ranges"][col][1])]
        return PredictionResult(fertilizer=ranked[0][0], confidence=float(ranked[0][1]),
                                top3=[{"label": c, "p": round(float(p), 3)} for c, p in ranked[:3]],
                                ood_fields=ood, model_version=self.meta.get("model_version", ""))
```

### Edge cases

| Case | Behaviour |
| --- | --- |
| Artifact missing | App starts; predictor shows a banner and disables submit; `/predict` → 503 page |
| Tampered soil/crop value | Form validation error (not a model call) |
| All inputs OOD | Prediction shown with amber warning listing every field |
| Confidence < 0.4 | Grey badge "Low confidence"; chat suggestion chip "Why is confidence low?" |

---

## 10.3 Dosage, cost and schedule

Rule-based and transparent. It turns a crop's recommended dose (RD) and the predicted fertilizer into product quantities, cost and a split schedule.

### 10.3.1 Inputs

| Input | Source |
| --- | --- |
| `crop` | Prediction input |
| `fertilizer` | Predicted class (primary product) |
| `area_value`, `area_unit` | Form (`acre` default, or `ha`) |
| `ratings` | Form: `{"N": "Low"|"Medium"|"High", "P": …, "K": …}`, default Medium |
| RD + N split + `avoid_chloride` | `data/crop_requirements.json` |
| Nutrient %, bag size, price | `data/fertilizer_products.json` |

### 10.3.2 Algorithm

1. **Recommended dose.** Read RD for the crop: N, P₂O₅, K₂O in kg/ha.
2. **Soil-test adjustment.** Multiply each nutrient by its rating factor: Low × 1.25, Medium × 1.00, High × 0.75. Result = target (kg/ha). This mirrors the common Soil Health Card practice of raising the dose by about a quarter on low-testing soils and cutting it on high-testing ones.
3. **Primary product.** If the predicted fertilizer is not Urea, apply it at the largest rate that does not exceed the target of any nutrient it contains: `qty = min(target[n] / pct[n] for nutrients with pct > 0)`. Example: DAP on wheat is limited by P₂O₅ (60 / 0.46 = 130.4 kg/ha), not N.
4. **Fill gaps** in this order, each only if the gap is more than 0.5 kg/ha:
   1. P₂O₅ gap → DAP (gap / 0.46). DAP's nitrogen counts toward N.
   2. K₂O gap → MOP (gap / 0.60), or SOP (gap / 0.50) when the crop has `avoid_chloride: true` (tobacco); add a note.
   3. N gap → Urea (gap / 0.46).
5. **Surplus check.** If any nutrient supplied exceeds its target by more than 10 %, add a note.
6. **Area and cost.** `ha = acres × 0.404686`. For each product: `kg_total = kg_per_ha × ha`, `bags = kg_total / bag_kg` (display 2 decimals and rounded up), `cost = kg_total × price_per_bag / bag_kg`. Total cost = sum.
7. **Schedule.** All non-urea products go at basal. Urea is split across the crop's N stages: stage need = `target_N × stage_pct`, minus the N from basal products for the first stage (floor 0); urea quantities are then scaled so the stages add up to the total urea.

### 10.3.3 Reference implementation

The agent should port this to `services/dosage_service.py`, reading `PRODUCTS` and `CROPS` from the JSON files instead of the inline dictionaries.

```python
# services/dosage_service.py (reference — verified against the test cases in §10.3.5)
from __future__ import annotations
import math

ACRE_TO_HA = 0.404686
RATING_FACTOR = {"Low": 1.25, "Medium": 1.0, "High": 0.75}

PRODUCTS = {
    "Urea":     {"N": 46, "P2O5": 0,  "K2O": 0,  "bag_kg": 45, "price_per_bag": 266.50},
    "DAP":      {"N": 18, "P2O5": 46, "K2O": 0,  "bag_kg": 50, "price_per_bag": 1350.00},
    "MOP":      {"N": 0,  "P2O5": 0,  "K2O": 60, "bag_kg": 50, "price_per_bag": 1710.54},
    "SOP":      {"N": 0,  "P2O5": 0,  "K2O": 50, "bag_kg": 50, "price_per_bag": 3500.00},
    "10-26-26": {"N": 10, "P2O5": 26, "K2O": 26, "bag_kg": 50, "price_per_bag": 1814.82},
    "14-35-14": {"N": 14, "P2O5": 35, "K2O": 14, "bag_kg": 50, "price_per_bag": 1700.00},
    "17-17-17": {"N": 17, "P2O5": 17, "K2O": 17, "bag_kg": 50, "price_per_bag": 1500.00},
    "20-20":    {"N": 20, "P2O5": 20, "K2O": 0,  "bag_kg": 50, "price_per_bag": 1300.00},
    "28-28":    {"N": 28, "P2O5": 28, "K2O": 0,  "bag_kg": 50, "price_per_bag": 1700.00},
}

CROPS = {
    "Wheat": {"rd": {"N": 120, "P2O5": 60, "K2O": 40}, "avoid_chloride": False,
              "n_split": [("Basal (at sowing)", 50), ("First irrigation / crown root initiation (20–25 days)", 50)]},
    "Tobacco": {"rd": {"N": 60, "P2O5": 60, "K2O": 60}, "avoid_chloride": True,
                "n_split": [("Basal (at planting)", 50), ("25–30 days after planting", 50)]},
    "Sugarcane": {"rd": {"N": 250, "P2O5": 115, "K2O": 115}, "avoid_chloride": False,
                  "n_split": [("Basal (at planting)", 0), ("30 days", 33), ("60 days", 33), ("90 days", 34)]},
    "Pulses": {"rd": {"N": 20, "P2O5": 50, "K2O": 20}, "avoid_chloride": False,
               "n_split": [("Basal (at sowing)", 100)]},
}

NUTS = ("N", "P2O5", "K2O")
def compute_dosage(crop: str, fertilizer: str, area_value: float, area_unit: str = "acre",
                   ratings: dict | None = None, products=PRODUCTS, crops=CROPS) -> dict:
    ratings = ratings or {}
    c = crops[crop]
    # Step 2: adjusted targets (kg/ha)
    target = {
        "N": c["rd"]["N"] * RATING_FACTOR[ratings.get("N", "Medium")],
        "P2O5": c["rd"]["P2O5"] * RATING_FACTOR[ratings.get("P", "Medium")],
        "K2O": c["rd"]["K2O"] * RATING_FACTOR[ratings.get("K", "Medium")],
    }
    supplied = {n: 0.0 for n in NUTS}
    qty = {}  # product -> kg/ha
    notes = []

    def add(product, kg):
        if kg <= 0:
            return
        qty[product] = qty.get(product, 0.0) + kg
        for n in NUTS:
            supplied[n] += kg * products[product][n] / 100

    # Step 3: primary product = predicted fertilizer, limited by the first nutrient it would exceed
    if fertilizer != "Urea":
        p = products[fertilizer]
        limits = [target[n] / (p[n] / 100) for n in NUTS if p[n] > 0]
        add(fertilizer, min(limits))
    # Step 4: fill gaps in order P -> K -> N
    gap = lambda n: target[n] - supplied[n]
    if gap("P2O5") > 0.5:
        add("DAP", gap("P2O5") / 0.46)
    if gap("K2O") > 0.5:
        k_src = "SOP" if c["avoid_chloride"] else "MOP"
        add(k_src, gap("K2O") / (products[k_src]["K2O"] / 100))
        if k_src == "SOP":
            notes.append("Potash from SOP, not MOP: this crop is chloride-sensitive.")
    if gap("N") > 0.5:
        add("Urea", gap("N") / 0.46)
    for n in NUTS:
        if supplied[n] > target[n] * 1.10:
            notes.append(f"{n} supplied {supplied[n]:.0f} kg/ha exceeds target {target[n]:.0f} kg/ha.")

    # Step 5: area, bags, cost
    ha = area_value * ACRE_TO_HA if area_unit == "acre" else area_value
    lines, total = [], 0.0
    for prod, kgha in qty.items():
        pr = products[prod]
        kg_total = kgha * ha
        cost = kg_total * pr["price_per_bag"] / pr["bag_kg"]
        total += cost
        lines.append({"product": prod, "kg_per_ha": round(kgha, 1), "kg_total": round(kg_total, 1),
                      "bags": round(kg_total / pr["bag_kg"], 2),
                      "bags_rounded": math.ceil(round(kg_total / pr["bag_kg"], 2)), "cost": round(cost)})

    # Step 6: schedule. Non-urea products all basal; urea split by crop N split after crediting basal N.
    basal_n = sum(kg * products[p]["N"] / 100 for p, kg in qty.items() if p != "Urea")
    urea_n_total = qty.get("Urea", 0.0) * 0.46
    raw = []
    for i, (stage, pct) in enumerate(c["n_split"]):
        need = target["N"] * pct / 100
        if i == 0:
            need -= basal_n
        raw.append(max(0.0, need))
    s = sum(raw)
    schedule = []
    for i, (stage, _pct) in enumerate(c["n_split"]):
        items = []
        if i == 0:
            items += [f"{p}: {qty[p] * ha:.1f} kg" for p in qty if p != "Urea"]
        if urea_n_total > 0 and s > 0 and raw[i] > 0:
            urea_kg = urea_n_total * raw[i] / s / 0.46 * ha
            items.append(f"Urea: {urea_kg:.1f} kg")
        if items:
            schedule.append({"stage": stage, "items": items})

    return {"area_ha": round(ha, 4), "targets_kg_ha": {k: round(v, 1) for k, v in target.items()},
            "lines": lines, "total_cost": round(total), "schedule": schedule, "notes": notes}
```

### 10.3.4 Worked example (must be a passing test)

Wheat, 2 acres (0.8094 ha), ratings Medium, predicted DAP. Target 120-60-40 kg/ha.

| Product | kg/ha | kg for 2 acres | Bags | Cost (₹) |
| --- | --- | --- | --- | --- |
| DAP | 130.4 | 105.6 | 2.11 (3) | 2,850 |
| MOP | 66.7 | 54.0 | 1.08 (2) | 1,846 |
| Urea | 209.8 | 169.8 | 3.77 (4) | 1,006 |
| **Total** | | | | **5,702** |

Schedule: Basal — DAP 105.6 kg, MOP 54.0 kg, Urea 64.3 kg. First irrigation (20–25 days) — Urea 105.6 kg.

### 10.3.5 More test cases (verified with the reference code)

| Case | Expected |
| --- | --- |
| Wheat, 2 acres, predicted Urea | Same quantities as DAP case (P via DAP, K via MOP, rest Urea), total ₹5,702 |
| Wheat, 1 ha, 17-17-17 | 17-17-17 235.3, DAP 43.5, Urea 156.9 kg/ha; total ₹9,162 (17-17-17 limited by K₂O 40/0.17) |
| Wheat, 2 acres, DAP, N Low / P High / K Medium | Targets 150-45-40; DAP 79.2 kg, MOP 54.0 kg, Urea 232.9 kg; total ₹5,363 |
| Tobacco, 1 acre, 28-28 | 28-28 86.7 kg + SOP 48.6 kg (not MOP); note about chloride; total ₹6,348 |
| Sugarcane, 1 acre, 10-26-26 | 10-26-26 179.0 kg basal; Urea 181.0 kg split 59.7 / 59.7 / 61.5 kg at 30/60/90 days |
| Pulses, 1 ha, 14-35-14 | 14-35-14 142.9 kg only (meets 20-50-20 exactly); total ₹4,857 |
| Wheat, 1 ha, 20-20 | 20-20 300 kg + MOP 66.7 kg basal; Urea 130.4 kg at first irrigation |

Prices used: Urea ₹266.50/45 kg, DAP ₹1,350/50 kg, MOP ₹1,710.54/50 kg, 10-26-26 ₹1,814.82/50 kg; others are placeholders flagged `price_verified: false` (14-35-14 ₹1,700, 17-17-17 ₹1,500, 20-20 ₹1,300, 28-28 ₹1,700, SOP ₹3,500). Tests should load prices from a fixture, not the live JSON.

### 10.3.6 Crop requirements (`data/crop_requirements.json`)

Typical general recommendations for irrigated crops in India (kg/ha). They vary by state, variety and season; verify against your state agriculture department's package of practices before the demo and keep them identical to `knowledge_base/crops/*.md`.

| Crop (model label) | N | P₂O₅ | K₂O | N split (stage: % of N) | Flags / extra notes |
| --- | --- | --- | --- | --- | --- |
| Paddy | 120 | 60 | 40 | Basal 50 · Active tillering (20–25 days after transplanting) 25 · Panicle initiation (45–50 days) 25 | Zinc sulphate 25 kg/ha on zinc-deficient soils |
| Wheat | 120 | 60 | 40 | Basal 50 · First irrigation / crown root initiation (20–25 days) 50 | Zinc on deficient soils |
| Maize | 120 | 60 | 40 | Basal 33 · Knee-high (25–30 days) 33 · Tasselling (50–55 days) 34 | Zinc on deficient soils |
| Cotton | 100 | 50 | 50 | Basal 34 · Squaring (40–45 days) 33 · Flowering (70–75 days) 33 | — |
| Sugarcane | 250 | 115 | 115 | Basal 0 · 30 days 33 · 60 days 33 · 90 days 34 | Long-duration crop; N only as top dressing |
| Barley | 60 | 30 | 20 | Basal 50 · First irrigation (25–30 days) 50 | — |
| Millets | 60 | 30 | 30 | Basal 50 · 25–30 days 50 | Values for finger/pearl millet under irrigation |
| Pulses | 20 | 50 | 20 | Basal 100 | Rhizobium + PSB seed treatment; sulphur 20 kg/ha |
| Ground Nuts | 20 | 40 | 40 | Basal 100 | Gypsum 400–500 kg/ha at flowering/pegging (40–45 days) |
| Oil seeds | 80 | 40 | 40 | Basal 50 · First irrigation (25–30 days) 50 | Based on mustard; sulphur 20–40 kg/ha |
| Tobacco | 60 | 60 | 60 | Basal 50 · 25–30 days after planting 50 | `avoid_chloride: true` → SOP instead of MOP |

JSON shape per crop:

```json
"Paddy": {
  "display": "Paddy (Rice)",
  "rd": {"N": 120, "P2O5": 60, "K2O": 40},
  "avoid_chloride": false,
  "n_split": [
    {"stage": "Basal (at transplanting)", "pct": 50},
    {"stage": "Active tillering (20–25 days after transplanting)", "pct": 25},
    {"stage": "Panicle initiation (45–50 days)", "pct": 25}
  ],
  "extra_notes": ["Apply zinc sulphate 25 kg/ha once in 2–3 seasons on zinc-deficient soils."]
}
```

Add SOP to `data/fertilizer_products.json`: `"SOP": {"N": 0, "P2O5": 0, "K2O": 50, "S": 18, "bag_kg": 50, "price_per_bag": 3500.00, "price_verified": false}`.

### 10.3.7 Display rules

- kg/ha one decimal; farm kg one decimal; bags two decimals plus "(≈ N bags)" rounded up; cost whole rupees with Indian grouping.
- Footer: "Approximate. Based on general recommendations and configured prices (as of <price_as_of>). Confirm with a soil test and your dealer."
- Show `extra_notes` and algorithm `notes` as a bulleted list under the table.

---

## 10.4 RAG chat assistant

### 10.4.1 Knowledge base format

Each file in `knowledge_base/` is Markdown with YAML front matter:

```markdown
---
title: Urea (46-0-0)
category: fertilizer        # fertilizer | crop | soil | practice | safety | faq | system
tags: [nitrogen, urea, top dressing]
applies_to: [Urea]          # model labels this doc is about (used for score boosting)
last_reviewed: 2026-11-06
---
# Urea (46-0-0)
## What it is
...
```

Files whose name starts with `_` (e.g. `_INDEX.md`) are not indexed.

### 10.4.2 Chunking

- Split on `## ` headings; each section is a unit.
- Pack paragraphs (and whole list blocks/tables) into chunks of ≤ 800 characters; overlap 150 characters between consecutive chunks of the same section.
- Prefix: `"{title} — {heading}\n"`.
- Skip chunks under 80 characters (merge into the previous one).

### 10.4.3 Retrieval

```python
def search(self, question: str, k: int, boost_labels: set[str]) -> list[Hit]:
    q = self.llm.embed([question], task_type="RETRIEVAL_QUERY")[0]   # 768-d
    q = q / np.linalg.norm(q)
    scores, idx = self.index.search(q[None, :].astype("float32"), k * 3)
    hits = []
    for s, i in zip(scores[0], idx[0]):
        if i < 0: continue
        ch = self.chunks[i]
        if set(ch.get("applies_to", [])) & boost_labels:
            s += 0.05
        hits.append(Hit(chunk=ch, score=float(s)))
    hits.sort(key=lambda h: -h.score)
    # keep at most 2 chunks per source for diversity
    out, per_src = [], {}
    for h in hits:
        if h.score < self.min_score: continue
        if per_src.get(h.chunk["source"], 0) >= 2: continue
        per_src[h.chunk["source"]] = per_src.get(h.chunk["source"], 0) + 1
        out.append(h)
        if len(out) == k: break
    return out
```

`boost_labels` = `{prediction.fertilizer, prediction.crop_type}`.

### 10.4.4 Prompt (use verbatim)

**System instruction**

```text
You are "Krishi Advisor", an agricultural extension assistant for Indian farmers inside the Smart Fertilizer Advisor app.

Rules:
1. Answer ONLY using the numbered PASSAGES and the FARMER CONTEXT below. Do not use outside knowledge.
2. If the passages do not contain the answer, reply exactly with the NO_ANSWER message provided and nothing else.
3. Never invent doses, prices, dates or product names. Use the numbers in the context and passages only.
4. Be practical and short: at most 150 words, simple sentences, bullet points for steps.
5. Cite the passages you used as [1], [2] at the end of the sentence they support.
6. If the question is about pesticides, human or animal health, loans, or anything unrelated to crop nutrition and this recommendation, politely say you can only help with fertilizer and crop nutrition questions.
7. If the context shows out-of-range inputs or low confidence (< 40%), mention that the recommendation is less certain and suggest a soil test.
8. Reply in {language_name}. Keep fertilizer names (Urea, DAP, MOP, 10-26-26), numbers and units in English digits.
9. Close with one line: "Please confirm with your local agriculture officer." translated into {language_name}.
```

**User content**

```text
FARMER CONTEXT
- Crop: {crop_display} | Soil: {soil} | Location: {location or "not given"}
- Temperature {temperature} °C, Humidity {humidity} %, Soil moisture {moisture} %
- Soil test values (dataset scale): N {nitrogen}, P {phosphorous}, K {potassium}; ratings N {rating_n}, P {rating_p}, K {rating_k}
- Recommended fertilizer: {fertilizer} (confidence {confidence_pct}%); alternatives: {alt_list}
- Out-of-range inputs: {ood_list or "none"}
- Dosage for {area_value} {area_unit}: {dosage_lines}   e.g. "DAP 105.6 kg (₹2,850); MOP 54.0 kg (₹1,846); Urea 169.8 kg (₹1,006)"
- Schedule: {schedule_lines}

PASSAGES
[1] ({source} — {heading}) {text}
[2] ...

NO_ANSWER message: {no_answer_text}

QUESTION
{question}
```

Generation config: `temperature=0.2`, `max_output_tokens=600`, timeout `LLM_TIMEOUT_S`.

### 10.4.5 Answer post-processing

1. Strip leading/trailing whitespace.
2. Extract cited numbers `[n]`; `sources` = cited passages (if none cited, all passages used).
3. If the model returned the NO_ANSWER text, return `sources: []`.
4. Escape HTML on render; allow line breaks and simple `- ` bullets (convert in JS, not with `innerHTML` of raw text).

### 10.4.6 Fallback

On `LLMError` (timeout, 429 after retry, 5xx, missing key):

```python
answer = LANG_MESSAGES[lang]["fallback"] + "\n\n" + "\n\n".join(
    f"[{i}] {h.chunk['title']} — {h.chunk['heading']}: {h.chunk['text'][:400]}…" for i, h in enumerate(hits, 1))
fallback = True
```

Retrieval itself needs an embedding call; if that also fails, use a keyword fallback: score chunks by count of question words (lower-cased, ≥ 4 letters) and return the top 3.

### 10.4.7 Suggested questions

`["Why this fertilizer?", "How and when do I apply it?", "What if it rains after applying?", "Is there an organic alternative?"]`; when confidence < 0.4 add "Why is the confidence low?". Translate chip labels when the language changes.

### 10.4.8 Quality checklist (run before the demo)

| Question | Must cite | Must mention |
| --- | --- | --- |
| Why DAP for my wheat? | `fertilizers/dap.md` or `crops/wheat.md` | phosphorus, basal |
| When do I apply urea? | `fertilizers/urea.md`, `crops/<crop>.md` | split doses, timing |
| What if it rains after applying? | `practices/weather-and-fertilizer.md` | avoid before heavy rain |
| Organic alternative? | `practices/integrated-nutrient-management.md` | FYM/compost, biofertilizers |
| Who won the cricket match? | none | polite refusal |
| How accurate is this model? | `system/about-this-system.md` | small dataset, ~96% CV, limits |

---

## 10.5 Multilingual answers

| Code | Language | `language_name` in prompt | Script font (PDF) |
| --- | --- | --- | --- |
| `en` | English | English | NotoSans |
| `te` | Telugu | Telugu (తెలుగు) | NotoSansTelugu |
| `ta` | Tamil | Tamil (தமிழ்) | NotoSansTamil |
| `hi` | Hindi | Hindi (हिन्दी) | NotoSansDevanagari |

Retrieval needs no translation: `gemini-embedding-001` is multilingual, so a Telugu question matches English passages. The answer language comes from the prompt instruction (rule 8).

`LANG_MESSAGES` (have a native speaker check these before the demo):

```python
LANG_MESSAGES = {
  "en": {"no_answer": "I don't have reliable information on that in my knowledge base. Please check with your local agriculture officer or Krishi Vigyan Kendra.",
         "fallback": "The AI service is unavailable right now. Here are the most relevant passages:"},
  "te": {"no_answer": "నా సమాచార భాండారంలో దీనిపై నమ్మదగిన సమాచారం లేదు. దయచేసి మీ స్థానిక వ్యవసాయ అధికారిని లేదా కృషి విజ్ఞాన కేంద్రాన్ని సంప్రదించండి.",
         "fallback": "AI సేవ ప్రస్తుతం అందుబాటులో లేదు. సంబంధిత సమాచారం ఇదిగో:"},
  "ta": {"no_answer": "இதைப் பற்றிய நம்பகமான தகவல் என் அறிவுத் தளத்தில் இல்லை. உங்கள் உள்ளூர் வேளாண் அலுவலரையோ கிருஷி விஞ்ஞான் கேந்திராவையோ அணுகவும்.",
         "fallback": "AI சேவை தற்போது கிடைக்கவில்லை. தொடர்புடைய பகுதிகள் இதோ:"},
  "hi": {"no_answer": "मेरे ज्ञान आधार में इस बारे में विश्वसनीय जानकारी नहीं है। कृपया अपने स्थानीय कृषि अधिकारी या कृषि विज्ञान केंद्र से संपर्क करें।",
         "fallback": "AI सेवा अभी उपलब्ध नहीं है। सबसे प्रासंगिक जानकारी यह है:"},
}
```

The fallback passages themselves stay in English (they are the source text).

---

## 10.6 PDF report

- Library: fpdf2. Page A4 portrait, margins 15 mm, auto page break.
- Fonts: register `NotoSans` (regular + bold) for Latin; for chat answers in `te`/`ta`/`hi`, switch to the matching Noto font for that cell. Enable text shaping (`pdf.set_text_shaping(True)`, requires the `uharfbuzz` package) for correct Indic rendering; if not installed, include only English messages and print the note "Regional-language answers are available in the app."
- Sections and order: see DESIGN §2.5.
- Tables via `pdf.table()` with header row shading (light green).
- Filename: `fertilizer-report-<id>.pdf`; built in memory (`bytes(pdf.output())`), never written to disk.
- Performance target < 2 s; truncate each chat answer to 600 characters.

---

## 10.7 Weather auto-fill

Behaviour is specified in API §5.3.3 and Integrations §13.3. UI rules:

- "Get weather" disabled until the location has ≥ 2 characters.
- Fills temperature (1 decimal) and humidity (integer); soil moisture stays manual (helper: "Measure or estimate; Open-Meteo soil moisture is not used").
- Sets hidden `weather_source=open-meteo`; editing either field afterwards sets it back to `manual`.
- Shows "Filled from Open-Meteo for <place> at <HH:MM>" under the section.

---

## 10.8 Accounts, history and dashboard

- Register: name 2–100 chars; email valid and unique (case-insensitive); password ≥ 8 chars with at least one letter and one digit; preferred language.
- Login: generic error message; `remember=True` when "Remember me" is ticked (cookie 14 days).
- History: newest first, 10 per page, filters not required.
- Dashboard: `count(predictions)`, `count(chat_messages where role='user')`, last prediction's fertilizer and date, last 5 rows.
- Clear history: POST with CSRF + confirm modal; deletes predictions (chats cascade); flash "History cleared".
