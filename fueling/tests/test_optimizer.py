import pytest

from fueling.services.optimizer import InfeasibleRouteError, plan_fuel_stops


def _cand(opis, mile, price):
    return {"opis_id": opis, "name": f"S{opis}", "city": "C", "state": "OK",
            "price": price, "lat": 0.0, "lng": 0.0, "miles_along_route": mile}


def test_sub_range_needs_no_stop():
    plan = plan_fuel_stops([_cand(1, 100, 4.0)], total_miles=300, range_mi=500, mpg=10)
    assert plan["stops"] == []
    assert plan["total_fuel_cost"] == 0.0


def test_single_stop_fill_to_destination():
    plan = plan_fuel_stops([_cand(1, 300, 4.0)], total_miles=600, range_mi=500, mpg=10)
    assert len(plan["stops"]) == 1
    assert plan["total_gallons"] == pytest.approx(60.0)
    assert plan["total_fuel_cost"] == pytest.approx(240.0)


def test_cheaper_ahead_buys_minimum():
    cands = [_cand(1, 100, 5.0), _cand(2, 200, 3.0)]
    plan = plan_fuel_stops(cands, total_miles=400, range_mi=250, mpg=10)
    by_id = {s["opis_id"]: s for s in plan["stops"]}
    assert by_id[1]["gallons_purchased"] == pytest.approx(20.0)  
    assert by_id[2]["gallons_purchased"] == pytest.approx(20.0)  
    assert plan["total_fuel_cost"] == pytest.approx(160.0)


def test_no_cheaper_ahead_fills_up():
    cands = [_cand(1, 100, 3.0), _cand(2, 200, 5.0)]
    plan = plan_fuel_stops(cands, total_miles=400, range_mi=250, mpg=10)
    by_id = {s["opis_id"]: s for s in plan["stops"]}
    assert by_id[1]["gallons_purchased"] == pytest.approx(35.0)
    assert by_id[2]["gallons_purchased"] == pytest.approx(5.0)
    assert plan["total_fuel_cost"] == pytest.approx(130.0)


def test_infeasible_gap_raises():
    with pytest.raises(InfeasibleRouteError):
        plan_fuel_stops([_cand(1, 100, 4.0)], total_miles=700, range_mi=500, mpg=10)