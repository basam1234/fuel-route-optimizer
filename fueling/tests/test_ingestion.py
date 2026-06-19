import pytest
from django.core.management import call_command

from fueling.models import FuelStation

FUEL = """OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
7,WOODSHED,"I-44, EXIT 283 & US-69",Big Cabin,OK,307,3.00
7,WOODSHED DUP,"I-44",Big Cabin,OK,307,3.10
9,KWIK TRIP,"I-94, EXIT 143",Tomah,WI,420,3.28
10,BADPRICE,"X",Tomah,WI,1,abc
11,NOCITY,"Y",Nowhereville,WI,2,3.50
"""

CITIES = """city,state_id,lat,lng,population
Big Cabin,OK,36.5,-95.2,300
Tomah,WI,43.9,-90.5,9000
"""


@pytest.mark.django_db
def test_ingestion_counts_dedupe_and_coords(tmp_path):
    fuel = tmp_path / "fuel.csv"
    cities = tmp_path / "cities.csv"
    fuel.write_text(FUEL)
    cities.write_text(CITIES)

    call_command("ingest_stations", csv=str(fuel), cities=str(cities))

    assert FuelStation.objects.count() == 2  
    big = FuelStation.objects.get(opis_id=7)
    assert big.name == "WOODSHED" 
    assert big.latitude == pytest.approx(36.5)
    assert big.longitude == pytest.approx(-95.2)