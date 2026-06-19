from dataclasses import dataclass
from threading import Lock

import numpy as np

from fueling.models import FuelStation

_lock = Lock()
_stations = None


@dataclass
class StationData:
    lats: np.ndarray
    lngs: np.ndarray
    prices: np.ndarray
    opis_ids: list
    names: list
    cities: list
    states: list

    def __len__(self) -> int:
        return len(self.opis_ids)


def load_stations(force_reload: bool = False) -> StationData:
    global _stations
    if _stations is not None and not force_reload:
        return _stations
    with _lock:
        if _stations is not None and not force_reload:
            return _stations
        rows = list(
            FuelStation.objects.values_list(
                "latitude", "longitude", "retail_price",
                "opis_id", "name", "city", "state",
            )
        )
        if rows:
            lats, lngs, prices, opis_ids, names, cities, states = zip(*rows)
        else:
            lats = lngs = prices = ()
            opis_ids = names = cities = states = ()
        _stations = StationData(
            lats=np.asarray(lats, dtype=np.float64),
            lngs=np.asarray(lngs, dtype=np.float64),
            prices=np.asarray(prices, dtype=np.float64),
            opis_ids=list(opis_ids),
            names=list(names),
            cities=list(cities),
            states=list(states),
        )
        return _stations