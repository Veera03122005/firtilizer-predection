import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTS_FILE = BASE_DIR / "data" / "fertilizer_products.json"
CROPS_FILE = BASE_DIR / "data" / "crop_requirements.json"

ACRE_TO_HA = 0.404686
RATING_FACTOR = {"Low": 1.25, "Medium": 1.0, "High": 0.75}
NUTS = ("N", "P2O5", "K2O")


def load_products_data() -> Dict[str, Any]:
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_crops_data() -> Dict[str, Any]:
    with open(CROPS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def get_price_as_of() -> str:
    try:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("_meta", {}).get("price_as_of", "2026-03")
    except Exception:
        return "2026-03"


def compute_dosage(
    crop: str,
    fertilizer: str,
    area_value: float,
    area_unit: str = "acre",
    ratings: Optional[Dict[str, str]] = None,
    products: Optional[Dict[str, Any]] = None,
    crops: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ratings = ratings or {}
    products = products or load_products_data()
    crops = crops or load_crops_data()

    if crop not in crops:
        raise ValueError(f"Crop '{crop}' not found in crop requirements.")

    c = crops[crop]
    # Step 2: adjusted targets (kg/ha)
    target = {
        "N": c["rd"]["N"] * RATING_FACTOR[ratings.get("N", "Medium")],
        "P2O5": c["rd"]["P2O5"] * RATING_FACTOR[ratings.get("P", "Medium")],
        "K2O": c["rd"]["K2O"] * RATING_FACTOR[ratings.get("K", "Medium")],
    }
    supplied = {n: 0.0 for n in NUTS}
    qty: Dict[str, float] = {}
    notes: List[str] = []

    def add(product: str, kg: float):
        if kg <= 0:
            return
        qty[product] = qty.get(product, 0.0) + kg
        for n in NUTS:
            supplied[n] += kg * products[product][n] / 100

    # Step 3: primary product = predicted fertilizer, limited by the first nutrient it would exceed
    if fertilizer != "Urea" and fertilizer in products:
        p = products[fertilizer]
        limits = [target[n] / (p[n] / 100) for n in NUTS if p.get(n, 0) > 0]
        if limits:
            add(fertilizer, min(limits))

    # Step 4: fill gaps in order P -> K -> N
    def gap(n: str) -> float:
        return target[n] - supplied[n]

    if gap("P2O5") > 0.5:
        add("DAP", gap("P2O5") / 0.46)

    if gap("K2O") > 0.5:
        avoid_cl = c.get("avoid_chloride", False)
        k_src = "SOP" if avoid_cl else "MOP"
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
    lines = []
    total = 0.0
    for prod, kgha in qty.items():
        pr = products[prod]
        kg_total = kgha * ha
        cost = kg_total * pr["price_per_bag"] / pr["bag_kg"]
        total += cost
        bags = round(kg_total / pr["bag_kg"], 2)
        lines.append({
            "product": prod,
            "kg_per_ha": round(kgha, 1),
            "kg_total": round(kg_total, 1),
            "bags": bags,
            "bags_rounded": math.ceil(bags),
            "cost": round(cost),
        })

    # Step 6: schedule. Non-urea products all basal; urea split by crop N split after crediting basal N.
    basal_n = sum(kg * products[p]["N"] / 100 for p, kg in qty.items() if p != "Urea")
    urea_n_total = qty.get("Urea", 0.0) * 0.46

    n_split = c.get("n_split", [])
    raw = []
    for i, item in enumerate(n_split):
        pct = item[1] if isinstance(item, (list, tuple)) else item["pct"]
        need = target["N"] * pct / 100
        if i == 0:
            need -= basal_n
        raw.append(max(0.0, need))

    s = sum(raw)
    schedule = []
    for i, item in enumerate(n_split):
        stage = item[0] if isinstance(item, (list, tuple)) else item["stage"]
        items = []
        if i == 0:
            items += [f"{p}: {qty[p] * ha:.1f} kg" for p in qty if p != "Urea"]
        if urea_n_total > 0 and s > 0 and raw[i] > 0:
            urea_kg = urea_n_total * raw[i] / s / 0.46 * ha
            items.append(f"Urea: {urea_kg:.1f} kg")
        if items:
            schedule.append({"stage": stage, "items": items})

    return {
        "area_ha": round(ha, 4),
        "targets_kg_ha": {k: round(v, 1) for k, v in target.items()},
        "lines": lines,
        "total_cost": round(total),
        "schedule": schedule,
        "notes": notes,
        "price_as_of": get_price_as_of(),
    }

