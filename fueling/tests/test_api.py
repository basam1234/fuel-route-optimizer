import re

import numpy as np
import pytest
import requests
import responses
from rest_framework.test import APIClient

from fueling.models import FuelStation
from fueling.services.routing import _haversine_cumulative

OSRM_RE = re.compile(r"https://router\.project-osrm\.org/route/v1/driving/.*")
NOMINATIM_RE = re.compile(r"https://nominatim\.openstreetmap\.org/search.*")


def _osrm_body(coords):
    return {"code": "Ok", "routes": [{"geometry": {"type": "LineString", "coordinates": coords}}]}


@responses.activate
@pytest.mark.django_db
def test_post_shape_called_once_and_geocoding_zero():
    coords = [[-75.0, 40.0], [-76.0, 39.5], [-77.0, 39.0]]  # sub-range => no stops
    responses.add(responses.GET, OSRM_RE, json=_osrm_body(coords), status=200)

    resp = APIClient().post(
        "/api/route/", {"start": "40.0,-75.0", "finish": "39.0,-77.0"}, format="json"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "start", "finish", "route", "fuel_stops",
        "total_gallons", "total_fuel_cost", "map_url", "external_calls",
    }
    assert body["external_calls"] == {"geocoding": 0, "routing": 1}
    assert body["fuel_stops"] == []
    assert len(responses.calls) == 1 


@responses.activate
@pytest.mark.django_db
def test_post_total_fuel_cost_single_stop():
    coords = [[-75.0 - i * 0.5, 40.0] for i in range(21)]  
    responses.add(responses.GET, OSRM_RE, json=_osrm_body(coords), status=200)
    FuelStation.objects.create(
        opis_id=1, name="MID", address="", city="Mid", state="OK",
        rack_id=1, retail_price=4.0, latitude=40.0, longitude=-80.0,
    )

    total = float(_haversine_cumulative(np.array(coords))[-1])
    expected = round((total / 10.0) * 4.0, 2) 

    resp = APIClient().post(
        "/api/route/", {"start": "40.0,-75.0", "finish": "40.0,-85.0"}, format="json"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["fuel_stops"]) == 1
    assert body["total_fuel_cost"] == pytest.approx(expected, abs=0.01)
    assert len(responses.calls) == 1


@pytest.mark.django_db
def test_bad_input_returns_400():
    resp = APIClient().post("/api/route/", {"start": "Dallas"}, format="json")
    assert resp.status_code == 400


@responses.activate
@pytest.mark.django_db
def test_geocode_miss_returns_400():
    responses.add(responses.GET, NOMINATIM_RE, json=[], status=200)
    resp = APIClient().post(
        "/api/route/", {"start": "Nowhere XYZ Town", "finish": "39.0,-77.0"}, format="json"
    )
    assert resp.status_code == 400


@responses.activate
@pytest.mark.django_db
def test_routing_service_error_returns_503():
    responses.add(responses.GET, OSRM_RE, body=requests.exceptions.ConnectionError("down"))
    resp = APIClient().post(
        "/api/route/", {"start": "40.0,-75.0", "finish": "39.0,-77.0"}, format="json"
    )
    assert resp.status_code == 503