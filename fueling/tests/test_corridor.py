import numpy as np

from fueling.data_cache import StationData
from fueling.services.corridor import candidates_along_route
from fueling.services.routing import _haversine_cumulative


def _route():
    coords = np.array([[-75.0 - i * 0.5, 40.0] for i in range(21)], dtype=np.float64)
    return {"coords": coords, "cumulative_miles": _haversine_cumulative(coords),
            "total_miles": float(_haversine_cumulative(coords)[-1])}


def _stations():
    return StationData(
        lats=np.array([40.0, 35.0]),
        lngs=np.array([-80.0, -100.0]),
        prices=np.array([3.0, 2.0]),
        opis_ids=[1, 2], names=["On", "Far"], cities=["A", "B"], states=["OK", "TX"],
    )


def test_on_route_included_far_excluded():
    cands = candidates_along_route(_route(), _stations(), corridor_miles=5)
    ids = [c["opis_id"] for c in cands]
    assert ids == [1]
    assert cands[0]["miles_along_route"] > 0


def test_bbox_padding_keeps_near_corridor_station():
    route = _route()
    stations = StationData(
        lats=np.array([40.0 + 3.0 / 69.0]),
        lngs=np.array([-80.0]),
        prices=np.array([3.0]),
        opis_ids=[9], names=["Near"], cities=["A"], states=["OK"],
    )
    assert len(candidates_along_route(route, stations, corridor_miles=5)) == 1