# Knowledge Base — Index and Review Checklist

This folder is the RAG source for the "Ask the Advisor" chat. Files starting with `_` (like this one) are **not indexed**.

## Structure

| Folder | Files | Purpose |
| --- | --- | --- |
| `fertilizers/` | urea, dap, mop, sop, ssp, npk-10-26-26, npk-14-35-14, npk-17-17-17, npk-20-20-0-13, npk-28-28-0 (10 files) | One profile per product the app predicts or uses in dosage |
| `crops/` | paddy, wheat, maize, cotton, sugarcane, barley, millets, pulses, groundnut, oilseeds, tobacco (11 files) | Nutrient needs and schedule for the 11 model crops |
| `soils/` | soil-types | The 5 soil types in the model |
| `practices/` | npk-basics-and-deficiency-symptoms, soil-testing-and-health-card, application-methods-and-timing, dosage-calculation, weather-and-fertilizer, integrated-nutrient-management, micronutrients-and-secondary-nutrients, fertilizer-safety-and-storage, buying-fertilizer | How-to and background topics |
| `faq/` | farmer-faq | Short answers to common questions |
| `system/` | about-this-system, glossary | How the app works, its limits, terms |

## Front matter (required in every indexed file)

```yaml
---
title: <display title>
category: fertilizer | crop | soil | practice | safety | faq | system
tags: [..]
applies_to: [<model labels: fertilizer classes or crop names, exact spelling>]
last_reviewed: YYYY-MM-DD
---
```

Exact model labels: fertilizers `Urea, DAP, 10-26-26, 14-35-14, 17-17-17, 20-20, 28-28`; crops `Barley, Cotton, Ground Nuts, Maize, Millets, Oil seeds, Paddy, Pulses, Sugarcane, Tobacco, Wheat`.

## Review checklist before the demo

These documents were drafted from general Indian agronomy guidance. Before relying on them:

- [ ] Every crop's N-P₂O₅-K₂O dose matches `data/crop_requirements.json` (the app's dosage table and the chat must agree).
- [ ] Doses checked against your state agriculture department's package of practices (Andhra Pradesh / Telangana / Tamil Nadu etc.) or ICAR/KVK guidance; adjust if your region differs.
- [ ] Prices are **not** stated in these documents on purpose (they change); the app takes them from `data/fertilizer_products.json`.
- [ ] Translations of product names in `system/glossary.md` checked by a native speaker.
- [ ] After any edit: `python rag/build_index.py`.

## Writing rules for new documents

- One topic per file; `##` sections of 2–6 short paragraphs or lists (each section becomes one or more chunks).
- Plain language, numbers with units (kg/ha, days after sowing).
- No prices, no brand names, no pesticide doses.
- If unsure of a number, leave it out rather than guess.
