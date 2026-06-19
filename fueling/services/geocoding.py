import re

import requests
from django.conf import settings
from django.core.cache import cache

_LATLNG_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


class GeocodeError(Exception):
    """No usable geocoding result for the input."""


class GeocodeServiceError(GeocodeError):
    """Upstream geocoder failed (timeout / connection / HTTP error)."""


def _parse_latlng(query: str):
    m = _LATLNG_RE.match(query)
    if not m:
        return None
    lat, lng = float(m.group(1)), float(m.group(2))
    if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0:
        return lat, lng
    return None


def resolve(query: str) -> tuple[float, float, int]:
    """Return (lat, lng, http_calls). http_calls is 0 for direct coords or cache hits, else 1."""
    direct = _parse_latlng(query)
    if direct is not None:
        return direct[0], direct[1], 0

    key = f"geocode:{query.strip().lower()}"
    cached = cache.get(key)
    if cached is not None:
        return cached[0], cached[1], 0

    params = {"q": query, "countrycodes": "us", "format": "jsonv2", "limit": 1}
    headers = {"User-Agent": settings.NOMINATIM_USER_AGENT}
    try:
        resp = requests.get(
            settings.NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=settings.EXTERNAL_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
        raise GeocodeServiceError(f"Geocoding service error for '{query}': {exc}") from exc

    if not data:
        raise GeocodeError(f"No geocoding result for '{query}'")

    lat = float(data[0]["lat"])
    lng = float(data[0]["lon"])
    cache.set(key, [lat, lng])
    return lat, lng, 1


def geocode(query: str) -> tuple[float, float]:
    lat, lng, _ = resolve(query)
    return lat, lng