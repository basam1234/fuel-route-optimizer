class InfeasibleRouteError(Exception):
    """Some leg exceeds the vehicle's range with no fuel stop in between."""


def _check_feasible(miles: list[float], total_miles: float, range_mi: float) -> None:
    prev = 0.0
    for m in miles:
        if m - prev > range_mi + 1e-9:
            raise InfeasibleRouteError(
                f"No fuel stop within {range_mi} mi between mile {prev:.1f} and {m:.1f}."
            )
        prev = m
    if total_miles - prev > range_mi + 1e-9:
        raise InfeasibleRouteError(
            f"No fuel stop within {range_mi} mi of the destination (mile {total_miles:.1f})."
        )


def plan_fuel_stops(candidates: list[dict], total_miles: float, range_mi: float, mpg: float) -> dict:
    if total_miles <= 0 or total_miles <= range_mi:
        return {"stops": [], "total_gallons": 0.0, "total_fuel_cost": 0.0}

    stops = sorted(candidates, key=lambda c: c["miles_along_route"])
    miles = [s["miles_along_route"] for s in stops]
    prices = [s["price"] for s in stops]
    _check_feasible(miles, total_miles, range_mi)

    n = len(stops)
    purchase = [0.0] * n  # tracked in miles and converted to gallons at the end
    tank = 0.0
    C = float(range_mi)
    D = float(total_miles)

    for i in range(n):
        here = miles[i]
        next_pos = miles[i + 1] if i + 1 < n else D
        reach = here + C

        target_dist = None
        for j in range(i + 1, n):
            if miles[j] > reach + 1e-9:
                break
            if prices[j] < prices[i] - 1e-12:
                target_dist = miles[j] - here
                break
        if target_dist is None and D <= reach + 1e-9:
            target_dist = D - here

        buy = max(0.0, target_dist - tank) if target_dist is not None else (C - tank)
        purchase[i] += buy
        tank += buy
        tank -= next_pos - here

    purchase[0] += miles[0]

    chosen = []
    total_cost = 0.0
    for i, s in enumerate(stops):
        if purchase[i] <= 1e-9:
            continue
        gallons = purchase[i] / mpg
        leg_cost = gallons * prices[i]
        total_cost += leg_cost
        chosen.append({**s, "gallons_purchased": gallons, "leg_cost": leg_cost})

    return {"stops": chosen, "total_gallons": D / mpg, "total_fuel_cost": total_cost}