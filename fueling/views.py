from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from fueling import data_cache
from fueling.serializers import RouteOptimizeResponseSerializer, RouteRequestSerializer
from fueling.services import corridor, geocoding, optimizer, routing


class EmptyCorridorError(Exception):
    pass


def _run_pipeline(start_q: str, finish_q: str) -> dict:
    try:
        s_lat, s_lng, c1 = geocoding.resolve(start_q)
    except geocoding.GeocodeError as exc:
        exc.field = "start"
        raise
    try:
        f_lat, f_lng, c2 = geocoding.resolve(finish_q)
    except geocoding.GeocodeError as exc:
        exc.field = "finish"
        raise
    geocoding_calls = c1 + c2

    route = routing.get_route((s_lat, s_lng), (f_lat, f_lng))
    routing_calls = 0 if route.get("from_cache") else 1
    total_miles = route["total_miles"]

        stations = data_cache.load_stations()
    needs_stops = total_miles > settings.VEHICLE_RANGE_MILES

    candidates = corridor.candidates_along_route(route, stations, settings.FUEL_CORRIDOR_MILES)
    try:
        if not candidates and needs_stops:
            raise optimizer.InfeasibleRouteError("empty corridor")
        plan = optimizer.plan_fuel_stops(
            candidates, total_miles, settings.VEHICLE_RANGE_MILES, settings.VEHICLE_MPG
        )
    except optimizer.InfeasibleRouteError:
        candidates = corridor.candidates_along_route(
            route, stations, settings.FUEL_CORRIDOR_WIDEN_MILES
        )
        if not candidates and needs_stops:
            raise EmptyCorridorError("No fuel stations found near this route.")
        plan = optimizer.plan_fuel_stops(
            candidates, total_miles, settings.VEHICLE_RANGE_MILES, settings.VEHICLE_MPG
        )

    return {
        "start": {"query": start_q, "lat": s_lat, "lng": s_lng},
        "finish": {"query": finish_q, "lat": f_lat, "lng": f_lng},
        "route": route,
        "plan": plan,
        "external_calls": {"geocoding": geocoding_calls, "routing": routing_calls},
    }


class RouteOptimizeView(APIView):
    def post(self, request):
        req = RouteRequestSerializer(data=request.data)
        if not req.is_valid():
            return Response(
                {"error": "invalid_input", "detail": req.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        start_q = req.validated_data["start"]
        finish_q = req.validated_data["finish"]

        try:
            result = _run_pipeline(start_q, finish_q)
        except geocoding.GeocodeServiceError as exc:
            return Response({"error": "geocoding_unavailable", "detail": str(exc)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except geocoding.GeocodeError as exc:
            field = getattr(exc, "field", "start")
            return Response({"error": "geocode_failed", "field": field, "detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        except routing.RoutingError as exc:
            return Response({"error": "routing_unavailable", "detail": str(exc)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except (optimizer.InfeasibleRouteError, EmptyCorridorError) as exc:
            return Response({"error": "no_feasible_plan", "detail": str(exc)},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception:
            return Response(
                {"error": "internal_error", "detail": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        plan = result["plan"]
        stops_out = [
            {
                "opis_id": s["opis_id"],
                "name": s["name"],
                "city": s["city"],
                "state": s["state"],
                "price_per_gallon": round(s["price"], 3),
                "miles_along_route": round(s["miles_along_route"], 1),
                "gallons_purchased": round(s["gallons_purchased"], 3),
                "leg_cost": round(s["leg_cost"], 2),
            }
            for s in plan["stops"]
        ]
        map_url = "/map/?" + urlencode({"start": start_q, "finish": finish_q})

        payload = {
            "start": result["start"],
            "finish": result["finish"],
            "route": {
                "total_distance_miles": round(result["route"]["total_miles"], 1),
                "geometry": result["route"]["geometry"],
            },
            "fuel_stops": stops_out,
            "total_gallons": round(plan["total_gallons"], 3),
            "total_fuel_cost": round(plan["total_fuel_cost"], 2),
            "map_url": map_url,
            "external_calls": result["external_calls"],
        }
        return Response(RouteOptimizeResponseSerializer(payload).data)


class MapView(APIView):
    def get(self, request):
        start_q = request.query_params.get("start", "").strip()
        finish_q = request.query_params.get("finish", "").strip()
        if not start_q or not finish_q:
            return render(request, "map.html",
                          {"route_geometry": None, "stops": [],
                           "error": "Provide ?start= and ?finish="})
        try:
            result = _run_pipeline(start_q, finish_q)
        except Exception as exc:
            return render(request, "map.html",
                          {"route_geometry": None, "stops": [], "error": str(exc)})

        stops = [
            {
                "lat": s["lat"],
                "lng": s["lng"],
                "name": s["name"],
                "city": s["city"],
                "state": s["state"],
                "price": round(s["price"], 3),
                "gallons": round(s["gallons_purchased"], 2),
            }
            for s in result["plan"]["stops"]
        ]
        return render(request, "map.html",
                      {"route_geometry": result["route"]["geometry"],
                       "stops": stops, "error": ""})