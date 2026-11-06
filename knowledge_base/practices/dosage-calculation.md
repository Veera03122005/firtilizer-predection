---
title: How the app calculates fertilizer quantity and cost
category: practice
tags: [dosage, quantity, cost, bags, acre, hectare, calculation]
applies_to: []
last_reviewed: 2026-11-06
---
# How the app calculates fertilizer quantity and cost

## Step by step

1. **Crop requirement.** The app starts from the crop's general recommended dose in kg of N, P₂O₅ and K₂O per hectare (for example wheat 120-60-40).
2. **Soil test rating.** Each nutrient is increased by 25% if your soil rating is Low, kept the same for Medium, and reduced by 25% for High.
3. **Recommended fertilizer first.** The predicted fertilizer is applied up to the point where the first of its nutrients reaches the target, so no nutrient is over-supplied.
4. **Fill the gaps.** Remaining phosphorus comes from DAP, remaining potassium from MOP (or SOP for tobacco), and remaining nitrogen from urea. Nitrogen from DAP and complexes is counted, so urea is reduced accordingly.
5. **Your farm area.** Quantities per hectare are multiplied by your area (1 acre = 0.4047 hectare).
6. **Bags and cost.** Quantity is divided by the bag size (urea 45 kg, others 50 kg) and multiplied by the configured price per bag.
7. **Schedule.** Non-urea products go at sowing; urea is split according to the crop's growth stages.

## Worked example

Wheat on 2 acres, Medium ratings, DAP recommended: DAP 105.6 kg, MOP 54.0 kg and urea 169.8 kg in total, about ₹5,702 at the configured prices. At sowing: DAP, MOP and about 64 kg urea; at the first irrigation: about 106 kg urea.

## Things to keep in mind

- Doses are general recommendations; your state's package of practices and your Soil Health Card take priority.
- Prices change and differ by dealer; the app shows the date of the configured prices. Never pay more than the MRP printed on the bag.
- Round bags up when buying, but apply the calculated quantity; store leftovers properly.
