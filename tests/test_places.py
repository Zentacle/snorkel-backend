"""Tests for the Place tree and the legacy builder (LOCATION_MIGRATION.md)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.helpers.get_localities import get_localities
from app.helpers.places import build_places_from_legacy, get_place_by_path
from app.models import DiveShop, Locality, Place, Spot


@pytest.fixture
def tree(db_session):
    us = Place.create("United States", "us", "country")
    hawaii = Place.create("Hawaii", "hi", "region", parent=us)
    maui = Place.create("Maui", "maui", "island", parent=hawaii)
    kihei = Place.create("Kihei", "kihei", "city", parent=maui)
    florida = Place.create("Florida", "fl", "region", parent=us)
    db_session.commit()
    return {"us": us, "hawaii": hawaii, "maui": maui, "kihei": kihei, "florida": florida}


# --- the Place model


def test_create_sets_path_lineage_and_depth(tree):
    kihei = tree["kihei"]
    assert kihei.path == "/loc/us/hi/maui/kihei"
    assert kihei.lineage == f"/{tree['us'].id}/{tree['hawaii'].id}/{tree['maui'].id}/{kihei.id}/"
    assert kihei.depth == 3
    assert tree["us"].depth == 0
    assert [p.slug for p in kihei.get_ancestors()] == ["us", "hi", "maui"]


def test_create_keeps_an_explicit_path(db_session, tree):
    town = Place.create("Vila Nova", "vila-nova", "city", parent=tree["hawaii"], path="/loc/us/hi/_/vila-nova")
    assert town.path == "/loc/us/hi/_/vila-nova"
    assert town.depth == 2


def test_create_rejects_unknown_kind(db_session):
    with pytest.raises(ValueError):
        Place.create("Atlantis", "atlantis", "lost_city")


def test_subtree_query_includes_self_and_descendants(tree):
    ids = {row.id for row in tree["hawaii"].subtree_ids_query()}
    assert ids == {tree["hawaii"].id, tree["maui"].id, tree["kihei"].id}


def test_spots_in_a_place(db_session, tree):
    in_kihei = Spot(name="Kamaole 2", is_verified=True, place_id=tree["kihei"].id)
    in_florida = Spot(name="Blue Heron Bridge", is_verified=True, place_id=tree["florida"].id)
    db_session.add_all([in_kihei, in_florida])
    db_session.commit()

    hawaii_spots = Spot.query.filter(Spot.place_id.in_(tree["hawaii"].subtree_ids_query())).all()
    assert hawaii_spots == [in_kihei]


def test_move_updates_subtree_lineage_but_not_urls(db_session, tree):
    tree["maui"].move_to(tree["florida"])
    db_session.commit()

    assert tree["kihei"].lineage.startswith(tree["florida"].lineage)
    assert tree["kihei"].depth == 3
    assert tree["kihei"].path == "/loc/us/hi/maui/kihei"  # URL unchanged
    assert {row.id for row in tree["hawaii"].subtree_ids_query()} == {tree["hawaii"].id}


def test_cannot_move_a_place_inside_itself(tree):
    with pytest.raises(ValueError):
        tree["hawaii"].move_to(tree["kihei"])


def test_slug_unique_per_parent(db_session, tree):
    Place.create("Kihei", "kihei", "city", parent=tree["florida"])  # same slug, other parent: fine
    db_session.commit()
    with pytest.raises(IntegrityError):
        Place.create("Kihei again", "kihei", "city", parent=tree["maui"], path="/loc/x")
    db_session.rollback()


def test_spot_url_never_depends_on_place(db_session, tree):
    spot = Spot(name="Shark's Cove", is_verified=True, place_id=tree["kihei"].id)
    db_session.add(spot)
    db_session.commit()
    assert spot.get_url() == f"/Beach/{spot.id}/sharks-cove"
    assert spot.get_simple_dict()["url"] == spot.get_url()


# --- building from the legacy tables


@pytest.fixture
def legacy(db_session, sample_country, sample_area_one, sample_area_two, sample_locality):
    gap_town = Locality(  # no county: legacy URL has "_"
        name="Vila Nova",
        short_name="vila-nova",
        country_id=sample_country.id,
        area_one_id=sample_area_one.id,
    )
    db_session.add(gap_town)
    db_session.flush()
    spot = Spot(
        name="Pier",
        is_verified=True,
        country_id=sample_country.id,
        area_one_id=sample_area_one.id,
        area_two_id=sample_area_two.id,
        locality_id=sample_locality.id,
    )
    gap_spot = Spot(name="Cove", is_verified=True, country_id=sample_country.id, locality_id=gap_town.id)
    region_shop = DiveShop(name="Shop", country_id=sample_country.id, area_one_id=sample_area_one.id)
    nowhere = Spot(name="Unplaced", is_verified=True)
    db_session.add_all([spot, gap_spot, region_shop, nowhere])
    db_session.commit()
    return {"gap_town": gap_town, "spot": spot, "gap_spot": gap_spot, "shop": region_shop}


def test_dry_run_writes_nothing(legacy):
    report = build_places_from_legacy()
    assert report["applied"] is False
    assert report["created"] == 5
    assert Place.query.count() == 0


def test_build_keeps_every_legacy_url(legacy, sample_locality):
    report = build_places_from_legacy(apply=True)
    assert report["created"] == 5
    assert {p.path for p in Place.query} == {
        "/loc/us",
        "/loc/us/ca",
        "/loc/us/ca/la",
        "/loc/us/ca/la/santa-monica",
        "/loc/us/ca/_/vila-nova",
    }
    # matches what the legacy API serves
    assert get_place_by_path("/loc/us/ca/la/santa-monica").path == sample_locality.get_dict()["url"]


def test_gap_town_hangs_off_its_region(legacy):
    build_places_from_legacy(apply=True)
    town = get_place_by_path("/loc/us/ca/_/vila-nova")
    assert town.parent.path == "/loc/us/ca"
    assert town.kind == "city"
    assert town.depth == 2


def test_spots_and_shops_get_their_most_specific_place(legacy):
    report = build_places_from_legacy(apply=True)
    assert legacy["spot"].place.path == "/loc/us/ca/la/santa-monica"
    assert legacy["gap_spot"].place.path == "/loc/us/ca/_/vila-nova"
    assert legacy["shop"].place.path == "/loc/us/ca"
    assert report["spots_assigned"] == 2
    assert report["spots_unplaced"] == 1
    assert report["shops_assigned"] == 1


def test_rebuild_is_idempotent(legacy, sample_area_one):
    build_places_from_legacy(apply=True)
    sample_area_one.name = "California (renamed)"
    report = build_places_from_legacy(apply=True)
    assert report.get("created", 0) == 0
    assert report.get("spots_assigned", 0) == 0
    assert get_place_by_path("/loc/us/ca").name == "California (renamed)"
    assert Place.query.count() == 5


def test_duplicate_urls_are_reported_not_written(db_session, legacy, sample_country, sample_area_one):
    clash = Locality(
        name="Vila Nova copy",
        short_name="vila-nova",
        country_id=sample_country.id,
        area_one_id=sample_area_one.id,
    )
    db_session.add(clash)
    db_session.commit()

    report = build_places_from_legacy(apply=True)
    assert report["duplicate_path"] == [(("locality", clash.id), "/loc/us/ca/_/vila-nova")]
    assert Place.query.count() == 5


# --- regression: geocoding crashed callers that unpack 4 values


def test_get_localities_returns_four_values(db_session):
    components = [
        {"long_name": "Kihei", "short_name": "Kihei", "types": ["locality"]},
        {"long_name": "Maui County", "short_name": "Maui County", "types": ["administrative_area_level_2"]},
        {"long_name": "Hawaii", "short_name": "HI", "types": ["administrative_area_level_1"]},
        {"long_name": "United States", "short_name": "US", "types": ["country"]},
    ]
    locality, area_two, area_one, country = get_localities(components)
    assert (locality.name, area_two.name, area_one.name, country.name) == (
        "Kihei",
        "Maui County",
        "Hawaii",
        "United States",
    )
