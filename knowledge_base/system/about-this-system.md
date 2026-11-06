---
title: About this system — how recommendations are made and their limits
category: system
tags: [model, accuracy, dataset, limitations, confidence, how it works, AI]
applies_to: []
last_reviewed: 2026-11-06
---
# About this system — how recommendations are made and their limits

## How the fertilizer recommendation is made

The recommended fertilizer comes from a machine-learning model (a random forest classifier) trained on a public "Fertilizer Prediction" dataset of 99 examples. It takes eight inputs: temperature, humidity, soil moisture, soil type, crop type, and Nitrogen, Phosphorous and Potassium values, and chooses one of seven fertilizers: Urea, DAP, 10-26-26, 14-35-14, 17-17-17, 20-20 (20-20-0-13) and 28-28 (28-28-0).

## How accurate is it?

In cross-validation on its 99-example dataset, the model chooses the dataset's fertilizer about 96% of the time; the exact figure is shown on the About page. This measures agreement with that small dataset only. It has not been tested against field trials, and a different dataset could give different results.

## What drives the recommendation

Almost all of the model's decision comes from the Nitrogen, Phosphorous and Potassium values. Temperature, humidity, soil moisture, soil type and crop type have very little influence in this dataset. The confidence percentage shows how strongly the model favours its choice; below about 40%, treat the recommendation as uncertain.

## What the N, P, K numbers mean

The dataset's Nitrogen, Phosphorous and Potassium values range only from 0 to 42 and are not laboratory soil-test values in kg/ha. In the data, a high Nitrogen value leads to Urea and a high Phosphorous value leads to DAP, so the values behave more like nutrient requirements than nutrients already present in the soil. The dataset's documentation does not state the units. When your values are outside the range seen in training, the app shows a warning.

## How quantities and costs are calculated

Quantities are not predicted by the AI model. They are calculated with standard agronomy rules from the crop's general recommended dose, your Low/Medium/High soil-test ratings and your farm area, and costs use configured prices. See "How the app calculates fertilizer quantity and cost".

## How the chat assistant works

The "Ask the Advisor" chat searches this knowledge base for passages related to your question, then an AI model (Google Gemini) writes an answer using only those passages and your recommendation details, and lists its sources. It does not change the recommendation or the doses. If it cannot find relevant information, it says so.

## Limitations and advice

- Educational tool, not a replacement for a soil test or expert advice.
- Doses are general recommendations; state packages of practices and your Soil Health Card take priority.
- Prices are estimates and change over time.
- Always confirm decisions with your local agriculture officer or Krishi Vigyan Kendra.
