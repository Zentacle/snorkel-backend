"""Location backfill for spots/shops with coordinates but no location, and
the get_localities fixes it relies on."""

import pytest

from app.helpers import location_backfill
from app.helpers.get_localities import get_localities
from app.helpers.location_backfill import backfill_locations
from app.models import AreaTwo, DiveShop, Locality, Spot


def components(locality=None, area_two=None, area_one=None, country=("United States", "US")):
    result = []
    if locality:
        result.append({"long_name": locality, "short_name": locality, "types": ["locality"]})
    if area_two:
        result.append({"long_name": area_two, "short_name": area_two, "types": ["administrative_area_level_2"]})
    if area_one:
        result.append({"long_name": area_one[0], "short_name": area_one[1], "types": ["administrative_area_level_1"]})
    if country:
        result.append({"long_name": country[0], "short_name": country[1], "types": ["country"]})
    return result


# --- get_localities


def test_missing_region_uses_underscore_not_none(db_session):
    locality, area_two, area_one, country = get_localities(
        components(locality="San Juan", country=("Puerto Rico", "PR"))
    )
    assert area_one is None and area_two is None
    assert locality.url == "/loc/pr/_/_/san-juan"


def test_repeat_lookups_reuse_rows_when_a_level_is_missing(db_session):
    first = get_localities(components(locality="Utila", area_two="Utila", country=("Honduras", "HN")))
    db_session.commit()
    second = get_localities(components(locality="Utila", area_two="Utila", country=("Honduras", "HN")))
    assert second[0] is first[0] and second[1] is first[1]
    assert Locality.query.count() == 1
    assert AreaTwo.query.count() == 1
    assert first[0].url == "/loc/hn/_/utila/utila"


def test_level_without_latin_name_is_treated_as_missing(db_session):
    locality, area_two, area_one, country = get_localities(
        components(locality="Al Wakrah", area_one=("الوكرة", "الوكرة"), country=("Qatar", "QA"))
    )
    assert area_one is None
    assert locality.url == "/loc/qa/_/_/al-wakrah"


def test_county_lookup_is_scoped_to_country(db_session):
    us = get_localities(components(area_two="Monroe County", area_one=("Florida", "FL")))
    db_session.commit()
    other = get_localities(components(area_two="Monroe County", area_one=("Florida", "FL"), country=("Uruguay", "UY")))
    assert other[1] is not us[1]


def test_no_country_returns_nothing(db_session):
    assert get_localities(components(locality="Nowhere", country=None)) == (None, None, None, None)


# --- backfill


@pytest.fixture
def located(db_session, sample_country, sample_area_one, sample_area_two, sample_locality):
    spot = Spot(
        name="Located",
        latitude=21.6500,
        longitude=-158.0600,
        is_verified=True,
        country_id=sample_country.id,
        area_one_id=sample_area_one.id,
        area_two_id=sample_area_two.id,
        locality_id=sample_locality.id,
    )
    db_session.add(spot)
    db_session.commit()
    return spot


def unlocated(db_session, name, lat, lng, **fields):
    spot = Spot(name=name, latitude=lat, longitude=lng, **{"is_verified": True, **fields})
    db_session.add(spot)
    db_session.commit()
    return spot


@pytest.fixture
def no_google(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Google must not be called")

    monkeypatch.setattr(location_backfill, "reverse_geocode", fail)


@pytest.fixture
def fake_google(monkeypatch):
    calls = []

    def geocode(lat, lng):
        calls.append((lat, lng))
        if lat > 50:
            return "ZERO_RESULTS", None
        return "OK", components(locality="Kailua-Kona", area_two="Hawaii County", area_one=("Hawaii", "HI"))

    monkeypatch.setattr(location_backfill, "reverse_geocode", geocode)
    monkeypatch.setattr(location_backfill.time, "sleep", lambda s: None)
    return calls


def test_nearby_spot_location_is_copied(db_session, located, no_google):
    near = unlocated(db_session, "Near", 21.6600, -158.0600)  # ~1.1 km
    report = backfill_locations(Spot, apply=True)
    assert report["nearby"] == 1
    assert near.locality_id == located.locality_id
    assert near.country_id == located.country_id


def test_far_spots_need_google_and_dry_run_writes_nothing(db_session, located, no_google):
    unlocated(db_session, "Far", 20.0, -155.9)
    report = backfill_locations(Spot)  # dry run: rolled back at the end
    assert report["applied"] is False
    assert report["needs_google"] == 1
    assert report["estimated_google_cost_usd"] == 0.01


def test_skips_deleted_unverified_and_no_coordinates(db_session, located, no_google):
    unlocated(db_session, "Deleted", 21.66, -158.06, is_deleted=True)
    unlocated(db_session, "Pending", 21.66, -158.06, is_verified=False)
    unlocated(db_session, "No coords", None, None)
    report = backfill_locations(Spot)
    assert report["targets"] == 0
    assert report["skipped_no_coordinates"] == 1


def test_google_fills_the_rest_and_reports_failures(db_session, located, fake_google):
    far = unlocated(db_session, "Kona reef", 19.64, -155.99)
    lost = unlocated(db_session, "Arctic", 80.0, 10.0)
    report = backfill_locations(Spot, apply=True, use_google=True)
    assert report["google"] == 1
    assert far.locality.name == "Kailua-Kona"
    assert far.locality.url == "/loc/us/hi/hawaii-county/kailua-kona"
    assert report["unresolved_ids"] == [lost.id]
    assert report["google_statuses"] == {"OK": 1, "ZERO_RESULTS": 1}


def test_google_results_become_neighbours_but_nearby_copies_do_not(db_session, located, fake_google):
    a = unlocated(db_session, "A", 19.640, -155.990)  # far from everything: Google
    b = unlocated(db_session, "B", 19.645, -155.990)  # ~0.6 km from A: copies A
    report = backfill_locations(Spot, apply=True, use_google=True)
    assert len(fake_google) == 1
    assert report["google"] == 1 and report["nearby"] == 1
    assert b.locality_id == a.locality_id

    # a spot 1 km from the copied B but 20 km from any real location must not chain off B


def test_nearby_copies_are_not_chained(db_session, located, no_google):
    # B is copied from the real location ~13 km away; C is ~2 km from B but
    # ~15.5 km from the real location, so it must not inherit via B
    unlocated(db_session, "B", 21.77, -158.06)
    unlocated(db_session, "C", 21.79, -158.06)
    report = backfill_locations(Spot)
    assert report["nearby"] == 1
    assert report["needs_google"] == 1


def test_limit(db_session, located, no_google):
    for i in range(3):
        unlocated(db_session, f"Near {i}", 21.66, -158.06)
    assert backfill_locations(Spot, limit=2)["targets"] == 2


def test_shops_are_backfilled_from_nearby_spots(db_session, located, no_google):
    shop = DiveShop(name="Shop", latitude=21.651, longitude=-158.061)
    db_session.add(shop)
    db_session.commit()
    report = backfill_locations(DiveShop, apply=True)
    assert report["nearby"] == 1
    assert shop.locality_id == located.locality_id


# --- matching the database's unique keys


def test_county_found_by_slug_even_when_google_renames_it(db_session):
    first = get_localities(components(area_two="Province of Agrigento", area_one=("Sicily", "Sicily")))
    first[1].short_name = "ag"
    db_session.commit()
    renamed = [
        {
            "long_name": "Free municipal consortium of Agrigento",
            "short_name": "AG",
            "types": ["administrative_area_level_2"],
        },
        {"long_name": "Sicily", "short_name": "Sicily", "types": ["administrative_area_level_1"]},
        {"long_name": "United States", "short_name": "US", "types": ["country"]},
    ]
    second = get_localities(renamed)
    assert second[1] is first[1]
    assert AreaTwo.query.count() == 1


def test_one_failing_item_is_skipped_and_reported(db_session, located, monkeypatch, sample_locality):
    a = unlocated(db_session, "Bad", 19.64, -155.99)
    b = unlocated(db_session, "Good", 40.0, -100.0)
    near = unlocated(db_session, "Near", 21.66, -158.06)  # pass 1 nearby match must survive

    def fake_get_localities(components):
        if components == "bad":
            # violates the unique url constraint
            return (Locality(name="Dup", short_name="dup", url=sample_locality.url), None, None, located.country)
        return (None, None, None, located.country)

    monkeypatch.setattr(location_backfill, "reverse_geocode", lambda lat, lng: ("OK", "bad" if lat < 20 else "good"))
    monkeypatch.setattr(location_backfill, "get_localities", fake_get_localities)
    monkeypatch.setattr(location_backfill.time, "sleep", lambda s: None)

    report = backfill_locations(Spot, apply=True, use_google=True)
    assert [item_id for item_id, _ in report["failed"]] == [a.id]
    assert report["google"] == 1 and report["nearby"] == 1
    assert b.country_id == located.country_id
    assert near.locality_id == located.locality_id
    assert a.country_id is None
