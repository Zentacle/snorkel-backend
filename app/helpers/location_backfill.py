"""Give spots and shops that have coordinates but no location
(country / area_one / area_two / locality) one, so they appear on location
pages. See scripts/backfill_locations.py.

Two methods, in order:
1. nearby: copy the location of the nearest already-located spot or shop
   within `max_km`. Free, works for offshore dive sites (where Google often
   has no town), and puts the item on the same pages as its neighbours.
2. google: reverse geocode with Google, then find or create the location
   rows (get_localities). Costs one API call per item.
"""

import math
import time
from collections import Counter, defaultdict

from sqlalchemy.exc import IntegrityError

from app.helpers.geocoding import reverse_geocode
from app.helpers.get_localities import get_localities
from app.models import DiveShop, Spot, db

LOCATION_COLUMNS = ("country_id", "area_one_id", "area_two_id", "locality_id")
EARTH_RADIUS_KM = 6371.0
COMMIT_EVERY = 50
# Google's Geocoding API list price, for the estimate printed by dry runs
GOOGLE_COST_PER_CALL_USD = 0.005


def _unlocated(model):
    return model.query.filter(*(getattr(model, column).is_(None) for column in LOCATION_COLUMNS))


def find_targets(model):
    """Live items with coordinates and no location, plus counts of the ones
    that can't be backfilled because they have no coordinates."""
    query = _unlocated(model)
    if model is Spot:
        query = query.filter(Spot.is_verified.isnot(False), Spot.is_deleted.isnot(True))
    items = query.order_by(model.id).all()
    with_coords = [item for item in items if item.latitude is not None and item.longitude is not None]
    return with_coords, len(items) - len(with_coords)


def _distance_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class LocatedIndex:
    """Located spots and shops bucketed by whole degree, for nearest lookups."""

    def __init__(self):
        self.cells = defaultdict(list)
        located_spots = Spot.query.filter(
            Spot.country_id.isnot(None),
            Spot.latitude.isnot(None),
            Spot.longitude.isnot(None),
            Spot.is_verified.isnot(False),
            Spot.is_deleted.isnot(True),
        )
        located_shops = DiveShop.query.filter(
            DiveShop.country_id.isnot(None), DiveShop.latitude.isnot(None), DiveShop.longitude.isnot(None)
        )
        for item in list(located_spots) + list(located_shops):
            self.add(item)

    def add(self, item):
        location = tuple(getattr(item, column) for column in LOCATION_COLUMNS)
        key = (math.floor(item.latitude), math.floor(item.longitude))
        self.cells[key].append((item.latitude, item.longitude, location))

    def nearest(self, latitude, longitude, max_km):
        """(location tuple, distance_km) of the nearest located item, or None.
        Checks the surrounding cells, enough for max_km up to ~100 km."""
        best = None
        base_lat, base_lng = math.floor(latitude), math.floor(longitude)
        for d_lat in (-1, 0, 1):
            for d_lng in (-1, 0, 1):
                for lat, lng, location in self.cells.get((base_lat + d_lat, base_lng + d_lng), []):
                    distance = _distance_km(latitude, longitude, lat, lng)
                    if distance <= max_km and (best is None or distance < best[1]):
                        best = (location, distance)
        return best


def backfill_locations(model, apply=False, use_google=False, limit=None, max_km=15.0, sleep=0.05):
    """Backfill locations for one model (Spot or DiveShop). Returns a report.

    Without apply, everything is rolled back at the end. Google is only
    called when use_google is set (it costs money even in a dry run).
    """
    targets, no_coords = find_targets(model)
    if limit:
        targets = targets[:limit]
    index = LocatedIndex()
    report = Counter(targets=len(targets), skipped_no_coordinates=no_coords, nearby=0, google=0, needs_google=0)
    unresolved = []
    failed = []
    google_statuses = Counter()
    samples = []

    def copy_nearby(item):
        match = index.nearest(item.latitude, item.longitude, max_km)
        if not match:
            return False
        location, distance = match
        for column, value in zip(LOCATION_COLUMNS, location):
            setattr(item, column, value)
        report["nearby"] += 1
        if len(samples) < 15:
            samples.append((item.id, item.name, "nearby", f"{distance:.1f} km"))
        return True

    # pass 1: free nearby matches
    pending = [item for item in targets if not copy_nearby(item)]

    # pass 2: Google for the rest. Only Google-resolved items are added to the
    # index (never nearby copies), so locations can't drift along a chain of
    # 15 km hops.
    for i, item in enumerate(pending, 1):
        if copy_nearby(item):
            continue
        if not use_google:
            report["needs_google"] += 1
            continue
        status, components = reverse_geocode(item.latitude, item.longitude)
        google_statuses[status] += 1
        if not components:
            unresolved.append(item.id)
        else:
            # one bad location row must not stop the run: isolate each item.
            # Flush first so earlier work (e.g. pass 1) isn't inside the savepoint.
            db.session.flush()
            country = None
            savepoint = db.session.begin_nested()
            try:
                locality, area_two, area_one, country = get_localities(components)
                if country:
                    item.country, item.area_one, item.area_two, item.locality = country, area_one, area_two, locality
                db.session.flush()
                savepoint.commit()
            except IntegrityError as error:
                savepoint.rollback()
                failed.append((item.id, str(error.orig).splitlines()[0]))
            else:
                if country:
                    index.add(item)
                    report["google"] += 1
                    if len(samples) < 30:
                        where = ", ".join(row.name for row in (locality, area_two, area_one, country) if row)
                        samples.append((item.id, item.name, "google", where))
                else:
                    unresolved.append(item.id)
        if apply and i % COMMIT_EVERY == 0:
            db.session.commit()
        time.sleep(sleep)

    if apply:
        db.session.commit()
    else:
        db.session.rollback()

    return {
        "model": model.__name__,
        "applied": apply,
        **report,
        "estimated_google_cost_usd": round(report["needs_google"] * GOOGLE_COST_PER_CALL_USD, 2),
        "google_statuses": dict(google_statuses),
        "unresolved_ids": unresolved,
        "failed": failed,
        "samples": samples,
    }
