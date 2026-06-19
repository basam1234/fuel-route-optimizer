# Fuel Route Optimizer

An API that plans a driving route between two locations in the USA and picks the cheapest places to refuel along the way. You give it a start and a finish, and it returns the route geometry, the fuel stops to make, how much fuel to buy at each one, and the total fuel cost for the trip.

The vehicle is assumed to have a 500 mile range and to do 10 miles per gallon, so a long trip needs several stops.

## What it does

Send a start and finish location. The API will:

1. Turn each location into coordinates.
2. Ask a routing service for the driving route once.
3. Find the truck stops that sit close to that route.
4. Work out the cheapest combination of stops that keeps the tank from running dry.
5. Return the route, the chosen stops, and the total fuel cost.

It leans on a single routing call per request. Geocoding the two endpoints and the routing call are all cached, so repeating the same trip costs zero external calls.

## How a request flows

```
start, finish
   -> geocode both endpoints (Nominatim, or read coordinates directly)
   -> one driving route from OSRM (full geometry + we measure distance ourselves)
   -> filter ~6,000 stations down to the ones near the route (NumPy)
   -> greedy fuel plan over the candidates
   -> response: route geometry, stops, gallons, total cost
```

The station list is loaded into memory once on first use and reused for every request, so the heavy work each time is one HTTP call plus a few milliseconds of vector math.

## Tech stack

- Python 3.12+
- Django 6.0 with Django REST Framework
- NumPy for the distance and corridor math
- requests for the two outside services
- OSRM public demo server for routing (no key)
- Nominatim for geocoding the endpoints (no key)
- Leaflet with OpenStreetMap tiles for the map page (no key)
- pandas for the one-off data ingestion command

Everything external is free and needs no API key.

## Running it locally

You need Python 3.12 or newer.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
```

Load the fuel station data (see the next section), then start the server:

```powershell
python manage.py runserver
```

The API is at `http://127.0.0.1:8000/api/route/` and the map page is at `http://127.0.0.1:8000/map/`.

## Loading the station data

The price file ships with addresses but no coordinates, so the ingestion command attaches a latitude and longitude to each station by matching its city and state against a free US cities dataset. This happens once, offline, so no geocoding calls are spent on the 6,000 stations.

```powershell
python manage.py ingest_stations --csv data/fuel-prices-for-be-assessment.csv --cities data/uscities.csv
```

The command prints a short report:

```
  rows read     : 8151
  after dedupe  : 6738
  geocode match : 6092
  inserted      : 6092
  skipped       : 646
  MATCH RATE    : 90.4%
```

It removes duplicate station IDs, matches each city to a coordinate, and skips the rows it cannot place (mostly small towns that are not in the free cities list). Re-running the command replaces the data, so it is safe to run again.

## API reference

### POST /api/route/

Request body:

```json
{
  "start": "Dallas, TX",
  "finish": "Chicago, IL"
}
```

You can pass a place name, an address, or raw coordinates as `"lat,lng"`. Passing coordinates skips the geocoding call.

Response:

```json
{
  "start":  { "query": "Dallas, TX", "lat": 32.7767, "lng": -96.7970 },
  "finish": { "query": "Chicago, IL", "lat": 41.8781, "lng": -87.6298 },
  "route": {
    "total_distance_miles": 925.4,
    "geometry": { "type": "LineString", "coordinates": [[-96.79, 32.77], "..."] }
  },
  "fuel_stops": [
    {
      "opis_id": 50,
      "name": "TA COUNCIL BLUFFS TRAVEL CENTER",
      "city": "Council Bluffs",
      "state": "IA",
      "price_per_gallon": 3.726,
      "miles_along_route": 410.2,
      "gallons_purchased": 42.1,
      "leg_cost": 156.91
    }
  ],
  "total_gallons": 92.54,
  "total_fuel_cost": 318.97,
  "map_url": "/map/?start=Dallas%2C+TX&finish=Chicago%2C+IL",
  "external_calls": { "geocoding": 2, "routing": 1 }
}
```

The `external_calls` block reports the outside calls this request actually made. Cache hits and coordinate inputs show up as zero, which is an easy way to confirm the one-call behaviour.

Example with curl:

```bash
curl -X POST http://127.0.0.1:8000/api/route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Dallas, TX", "finish": "Chicago, IL"}'
```

### Error responses

| Status | When it happens |
| ------ | --------------- |
| 400 | The body is missing a field, or a location could not be geocoded. |
| 422 | No set of stops can keep the trip inside the 500 mile range, even after widening the search. |
| 503 | The geocoding or routing service timed out or returned an error. |
| 500 | Anything unexpected. The body is clean JSON, never a raw stack trace. |

### GET /map/

Renders a Leaflet map of the route with a marker on each fuel stop. Open it directly with the same inputs:

```
http://127.0.0.1:8000/map/?start=Dallas,+TX&finish=Chicago,+IL
```

The root URL `/` redirects here.

## The fuel cost model

The plan treats the trip as a line from mile 0 to the total distance, with candidate stations placed at their distance along that line. It walks the stations in order and decides how much to buy at each one with a standard greedy rule:

- If a cheaper station sits within range ahead, buy just enough to reach it.
- If nothing cheaper is in range, fill the tank and carry that cheaper fuel forward.

This gives the lowest total cost for the trip while respecting the 500 mile range between fill-ups.

### Assumptions worth knowing for an audit

- **The tank starts empty and the truck pays for the whole trip.** Total gallons billed equals total miles divided by 10. This keeps the cost figure meaningful for every trip.
- **The first stop carries the cost of the opening leg.** The drive from the start point to the first station is billed at that first station, because that station is the earliest place fuel can be bought. As a result the first stop's `gallons_purchased` can read above the 50 gallon tank size. Read it as the total fuel bought for that opening segment, including the miles driven before the truck reaches the station.
- **Trips under 500 miles report no stops and zero fuel cost.** They fit inside one tank, so there is nothing to optimise.
- **Distance is measured along the route geometry with the haversine formula.** This runs a little under the true road distance, which keeps the route distance and the per-station mile markers on the same scale. For a closer total you could use the distance OSRM reports.
- **Stations are placed at their city centre.** City and state give a reliable match, while the raw addresses are highway exit descriptions that are hard to geocode. City level precision is enough to decide which stations sit near the route, and the price is what drives the result. About 10 percent of stations have no city match and are left out.

## Performance notes

- The station table is read from the database once and kept in memory as NumPy arrays. Later requests skip the database.
- A bounding box around the route trims the station list before any distance math runs.
- The route geometry is thinned to roughly two points per mile for the proximity check, which keeps long cross country routes fast without changing which stations qualify.
- Geocoding results and full routes are cached, so a repeated trip makes no outside calls.

## Tests

```powershell
pytest -q
```

The suite covers the greedy planner (cheaper ahead, forced fill, infeasible gaps, short trips), the corridor filter, the ingestion command, and the API end to end. Every test mocks the outside services with the `responses` library, so the suite runs offline and fast. One API test asserts the routing service is called exactly once.

## Project layout

```
config/                     Django project (settings, urls)
fueling/
  models.py                 FuelStation
  serializers.py            request and response shapes
  views.py                  the API and map views
  data_cache.py             in-memory station arrays
  services/
    geocoding.py            endpoint geocoding
    routing.py              the single OSRM call
    corridor.py             route proximity filter
    optimizer.py            greedy fuel plan
  management/commands/
    ingest_stations.py      CSV ingestion
  tests/
data/                       price CSV and the cities lookup
templates/map.html          Leaflet map page
```

## Data and attribution

Fuel prices come from the file supplied with the assignment. City coordinates come from the SimpleMaps US Cities database (Basic), which is free under CC BY 4.0. See https://simplemaps.com/data/us-cities.

Routing is served by the OSRM public demo server, and geocoding by Nominatim. Both ask for light, considerate use, which suits a single call per request with caching.
