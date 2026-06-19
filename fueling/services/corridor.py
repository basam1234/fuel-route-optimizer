import numpy as np

_EARTH_RADIUS_MILES = 3958.7613


def _haversine_to_all(lat0: float, lng0: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    lat0r = np.radians(lat0)
    lng0r = np.radians(lng0)
    latsr = np.radians(lats)
    lngsr = np.radians(lngs)
    dlat = latsr - lat0r
    dlng = lngsr - lng0r
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat0r) * np.cos(latsr) * np.sin(dlng / 2.0) ** 2
    return 2.0 * _EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


def candidates_along_route(route: dict, stations, corridor_miles: float) -> list[dict]:
    coords = route["coords"]
    cumulative = route["cumulative_miles"]
    if len(stations) == 0 or coords.shape[0] == 0:
        return []

    route_lng = coords[:, 0]
    route_lat = coords[:, 1]
    mean_lat = float(np.mean(route_lat))

    lat_pad = corridor_miles / 69.0
    cos_lat = max(np.cos(np.radians(mean_lat)), 1e-6)
    lng_pad = corridor_miles / (69.0 * cos_lat)

    lat_min, lat_max = route_lat.min() - lat_pad, route_lat.max() + lat_pad
    lng_min, lng_max = route_lng.min() - lng_pad, route_lng.max() + lng_pad

    s_lat, s_lng = stations.lats, stations.lngs
    in_box = (s_lat >= lat_min) & (s_lat <= lat_max) & (s_lng >= lng_min) & (s_lng <= lng_max)
    idxs = np.nonzero(in_box)[0]
    if idxs.size == 0:
        return []

    total = float(cumulative[-1]) if cumulative.size else 0.0
    stride = max(1, int(coords.shape[0] / (total * 2))) if total > 0 else 1
    keep = np.arange(0, coords.shape[0], stride)
    if keep[-1] != coords.shape[0] - 1:
        keep = np.append(keep, coords.shape[0] - 1)
    search_lat = route_lat[keep]
    search_lng = route_lng[keep]
    search_cum = cumulative[keep]

    out = []
    for i in idxs:
        dists = _haversine_to_all(s_lat[i], s_lng[i], search_lat, search_lng)
        nearest = int(np.argmin(dists))
        if dists[nearest] <= corridor_miles:
            out.append(
                {
                    "opis_id": stations.opis_ids[i],
                    "name": stations.names[i],
                    "city": stations.cities[i],
                    "state": stations.states[i],
                    "price": float(stations.prices[i]),
                    "lat": float(s_lat[i]),
                    "lng": float(s_lng[i]),
                    "miles_along_route": float(search_cum[nearest]),
                }
            )
    out.sort(key=lambda r: r["miles_along_route"])
    return out