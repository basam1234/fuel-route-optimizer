import numpy as np
import requests
from django.conf import settings
from django.core.cache import cache


_EARTH_RADIUS_MILES = 3958.7613


class RoutingError(Exception):
    """OSRM failed or returned a non-Ok route."""


def _haversine_cumulative(coords: np.ndarray) -> np.ndarray:
    if coords.shape[0] == 0:
        return np.zeros(0)
    lng = np.radians(coords[:, 0])
    lat = np.radians(coords[:, 1])
    dlat = np.diff(lat)
    dlng = np.diff(lng)
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlng / 2.0) ** 2
    seg = 2.0 * _EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))
    out = np.zeros(coords.shape[0])
    out[1:] = np.cumsum(seg)
    return out


def get_route(start: tuple, finish: tuple) -> dict:
    s_lat, s_lng = start
    f_lat, f_lng = finish
    key = f"route:{round(s_lat, 5)},{round(s_lng, 5)};{round(f_lat, 5)},{round(f_lng, 5)}"

    cached = cache.get(key)
    if cached is not None:
        coords = np.asarray(cached["coords"], dtype=np.float64)
        return {
            "geometry": cached["geometry"],
            "coords": coords,
            "cumulative_miles": _haversine_cumulative(coords),
            "total_miles": cached["total_miles"],
            "from_cache": True,
        }

    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{s_lng},{s_lat};{f_lng},{f_lat}"
    params = {"overview": "full", "geometries": "geojson"}
    try:
        resp = requests.get(url, params=params, timeout=settings.EXTERNAL_HTTP_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
        raise RoutingError(f"Routing service error: {exc}") from exc

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RoutingError(f"OSRM returned code={payload.get('code')!r}")

    geometry = payload["routes"][0]["geometry"]
    coords = np.asarray(geometry["coordinates"], dtype=np.float64)
    if coords.ndim != 2 or coords.shape[0] == 0:
        raise RoutingError("OSRM returned empty geometry")

    cumulative = _haversine_cumulative(coords)
    total_miles = float(cumulative[-1])

    cache.set(key, {"geometry": geometry, "coords": coords.tolist(), "total_miles": total_miles})
    return {
        "geometry": geometry,
        "coords": coords,
        "cumulative_miles": cumulative,
        "total_miles": total_miles,
        "from_cache": False,
    }