import re
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fueling.models import FuelStation

_CITY_VARIANTS = [
    (re.compile(r"\bST\.?\b"), "SAINT"),
    (re.compile(r"\bFT\.?\b"), "FORT"),
    (re.compile(r"\bMT\.?\b"), "MOUNT"),
]


def _normalize_city(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.upper().str.replace(r"\s+", " ", regex=True)
    for pattern, repl in _CITY_VARIANTS:
        s = s.str.replace(pattern, repl, regex=True)
    return s.str.strip()


class Command(BaseCommand):
    help = "Ingest truck-stop fuel prices and attach coordinates via an offline uscities join."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True, help="Path to the fuel prices CSV.")
        parser.add_argument("--cities", required=True, help="Path to uscities.csv.")

    def handle(self, *args, **options):
        csv_path = Path(options["csv"])
        cities_path = Path(options["cities"])
        if not csv_path.exists():
            raise CommandError(f"Fuel CSV not found: {csv_path}")
        if not cities_path.exists():
            raise CommandError(f"Cities CSV not found: {cities_path}")

        fuel = pd.read_csv(csv_path, dtype=str)
        fuel.columns = [c.strip() for c in fuel.columns]
        rows_read = len(fuel)

        fuel["retail_price"] = pd.to_numeric(fuel["Retail Price"], errors="coerce")
        fuel = fuel.dropna(subset=["retail_price"])
        fuel = fuel[fuel["retail_price"] > 0]

        fuel["opis_id"] = pd.to_numeric(fuel["OPIS Truckstop ID"], errors="coerce")
        fuel = fuel.dropna(subset=["opis_id"])
        fuel["opis_id"] = fuel["opis_id"].astype(int)
        fuel = fuel.drop_duplicates(subset=["opis_id"], keep="first")
        rows_deduped = len(fuel)

        fuel["state"] = fuel["State"].astype(str).str.strip().str.upper()
        fuel["city_key"] = _normalize_city(fuel["City"])

        cities = pd.read_csv(cities_path)
        cities["state_id"] = cities["state_id"].astype(str).str.strip().str.upper()
        cities["city_key"] = _normalize_city(cities["city"])
        cities["population"] = pd.to_numeric(cities.get("population"), errors="coerce").fillna(0)
        # One row per (city, state) keeps the join from fanning out; keep the biggest city.
        cities = (
            cities.sort_values("population", ascending=False)
            .drop_duplicates(subset=["city_key", "state_id"], keep="first")[
                ["city_key", "state_id", "lat", "lng"]
            ]
        )

        merged = fuel.merge(
            cities,
            left_on=["city_key", "state"],
            right_on=["city_key", "state_id"],
            how="left",
        )
        matched = merged.dropna(subset=["lat", "lng"]).copy()
        rows_matched = len(matched)
        skipped = rows_deduped - rows_matched

        matched["rack_id"] = pd.to_numeric(matched["Rack ID"], errors="coerce")

        records = []
        for row in matched.to_dict("records"):
            rack = row["rack_id"]
            address = row["Address"]
            records.append(
                FuelStation(
                    opis_id=int(row["opis_id"]),
                    name=str(row["Truckstop Name"])[:255],
                    address=("" if pd.isna(address) else str(address)[:255]),
                    city=str(row["City"]).strip()[:128],
                    state=str(row["state"])[:2],
                    rack_id=(None if pd.isna(rack) else int(rack)),
                    retail_price=float(row["retail_price"]),
                    latitude=float(row["lat"]),
                    longitude=float(row["lng"]),
                )
            )

        with transaction.atomic():
            FuelStation.objects.all().delete()
            FuelStation.objects.bulk_create(records, batch_size=1000)

        inserted = len(records)
        match_rate = (rows_matched / rows_deduped * 100.0) if rows_deduped else 0.0

        self.stdout.write(self.style.SUCCESS("Ingestion complete."))
        self.stdout.write(f"  rows read     : {rows_read}")
        self.stdout.write(f"  after dedupe  : {rows_deduped}")
        self.stdout.write(f"  geocode match : {rows_matched}")
        self.stdout.write(f"  inserted      : {inserted}")
        self.stdout.write(f"  skipped       : {skipped}")
        self.stdout.write(f"  MATCH RATE    : {match_rate:.1f}%")