import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

CACHE_TTL = 600  # 10 minutes
_cache: Dict[str, Tuple[float, Any]] = {}


class WeatherError(Exception):
    pass


def geocode(name: str, count: int = 5, timeout: int = 8) -> List[Dict[str, Any]]:
    cache_key = f"geo:{name.lower().strip()}"
    now = time.time()
    if cache_key in _cache and (now - _cache[cache_key][0] < CACHE_TTL):
        return _cache[cache_key][1]

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": name, "count": count, "language": "en", "format": "json"}
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        _cache[cache_key] = (now, results)
        return results
    except Exception as e:
        logger.warning(f"Geocoding failed for '{name}': {e}")
        raise WeatherError(f"Could not search locations: {str(e)}")


def current(lat: float, lon: float, timeout: int = 8) -> Dict[str, float]:
    cache_key = f"weather:{round(lat, 2)}:{round(lon, 2)}"
    now = time.time()
    if cache_key in _cache and (now - _cache[cache_key][0] < CACHE_TTL):
        return _cache[cache_key][1]

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m",
    }
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        curr = data.get("current", {})
        temp = float(curr.get("temperature_2m", 28.0))
        hum = float(curr.get("relative_humidity_2m", 60.0))
        res = {"temperature": temp, "humidity": hum}
        _cache[cache_key] = (now, res)
        return res
    except Exception as e:
        logger.warning(f"Weather lookup failed for ({lat}, {lon}): {e}")
        raise WeatherError(f"Could not fetch weather: {str(e)}")
