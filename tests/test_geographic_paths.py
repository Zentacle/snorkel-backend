"""Location migration step 1: stored node paths and pinned spot URLs."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.helpers.geographic_paths import backfill_node_paths
from app.models import GeographicNode, Locality, Spot
from app.services.url_mapping import URLMappingService


@pytest.fixture
def gap_locality(db_session, sample_country, sample_area_one):
    """A town with no county: its URL has a "_" for area_two."""
    locality = Locality(
        name="Vila Nova",
        short_name="vila-nova",
        country_id=sample_country.id,
        area_one_id=sample_area_one.id,
    )
    db_session.add(locality)
    db_session.commit()
    return locality


@pytest.fixture
def nodes(db_session, sample_country, sample_area_one, sample_area_two, sample_locality, gap_locality):
    """Nodes mirroring the legacy rows, the way the migration scripts build them."""
    country = GeographicNode(name="United States", short_name="us", admin_level=0, legacy_country_id=sample_country.id)
    db_session.add(country)
    db_session.flush()
    state = GeographicNode(
        name="California",
        short_name="ca",
        admin_level=1,
        parent_id=country.id,
        legacy_country_id=sample_country.id,
        legacy_area_one_id=sample_area_one.id,
    )
    db_session.add(state)
    db_session.flush()
    county = GeographicNode(
        name="Los Angeles County",
        short_name="la",
        admin_level=2,
        parent_id=state.id,
        legacy_country_id=sample_country.id,
        legacy_area_one_id=sample_area_one.id,
        legacy_area_two_id=sample_area_two.id,
    )
    db_session.add(county)
    db_session.flush()
    city = GeographicNode(
        name="Santa Monica",
        short_name="santa-monica",
        admin_level=3,
        parent_id=county.id,
        legacy_country_id=sample_country.id,
        legacy_area_one_id=sample_area_one.id,
        legacy_area_two_id=sample_area_two.id,
        legacy_locality_id=sample_locality.id,
    )
    gap_town = GeographicNode(
        name="Vila Nova",
        short_name="vila-nova",
        admin_level=3,
        parent_id=state.id,
        legacy_country_id=sample_country.id,
        legacy_area_one_id=sample_area_one.id,
        legacy_locality_id=gap_locality.id,
    )
    db_session.add_all([city, gap_town])
    db_session.commit()
    return {"country": country, "state": state, "county": county, "city": city, "gap_town": gap_town}


def test_spot_url_stays_on_beach_when_it_has_a_node(db_session, nodes):
    spot = Spot(name="Shark's Cove", is_verified=True, geographic_node_id=nodes["city"].id)
    db_session.add(spot)
    db_session.commit()

    assert spot.get_url() == f"/Beach/{spot.id}/sharks-cove"
    assert spot.get_simple_dict()["url"] == f"/Beach/{spot.id}/sharks-cove"
    assert spot.get_geographic_url() == f"/loc/us/ca/la/santa-monica/sharks-cove-{spot.id}"


def test_spot_without_node_has_no_geographic_url(sample_spot):
    assert sample_spot.get_geographic_url() is None


def test_legacy_url_keeps_underscore_for_missing_level(nodes, gap_locality):
    assert nodes["gap_town"].get_legacy_url() == "/loc/us/ca/_/vila-nova"
    assert nodes["gap_town"].get_legacy_url() == gap_locality.get_dict()["url"]
    assert nodes["city"].get_legacy_url() == "/loc/us/ca/la/santa-monica"


def test_backfill_dry_run_writes_nothing(nodes):
    report = backfill_node_paths()
    assert report["planned"] == 5
    assert report["applied"] is False
    assert all(node.path is None for node in nodes.values())


def test_backfill_apply_stores_current_urls(nodes):
    report = backfill_node_paths(apply=True)
    assert report["applied"] is True
    assert report["duplicate_paths"] == {}
    assert nodes["gap_town"].path == "/loc/us/ca/_/vila-nova"
    # tree-derived path would have dropped the "_"
    assert nodes["gap_town"].get_new_url() == "/loc/us/ca/vila-nova"
    assert nodes["gap_town"].get_url() == "/loc/us/ca/_/vila-nova"
    assert nodes["state"].get_url() == "/loc/us/ca"


def test_backfill_refuses_duplicate_paths(db_session, nodes, sample_locality):
    duplicate = GeographicNode(
        name="Santa Monica (dup)",
        short_name="santa-monica-dup",
        admin_level=3,
        parent_id=nodes["county"].id,
        legacy_locality_id=sample_locality.id,
    )
    db_session.add(duplicate)
    db_session.commit()

    report = backfill_node_paths(apply=True)
    assert report["applied"] is False
    assert sorted(report["duplicate_paths"]["/loc/us/ca/la/santa-monica"]) == sorted([nodes["city"].id, duplicate.id])
    assert nodes["city"].path is None


def test_find_node_by_stored_path_handles_gaps(nodes):
    backfill_node_paths(apply=True)
    assert URLMappingService.find_node_by_path(["us", "ca", "_", "vila-nova"]) == nodes["gap_town"]
    # depth-based traversal still works for full paths
    assert URLMappingService.find_node_by_path(["us", "ca", "la"]) == nodes["county"]


def test_short_name_unique_per_parent_not_globally(db_session, nodes):
    # another "la" under a different parent is fine
    db_session.add(GeographicNode(name="La", short_name="la", admin_level=3, parent_id=nodes["city"].id))
    db_session.commit()

    db_session.add(GeographicNode(name="LA again", short_name="la", admin_level=2, parent_id=nodes["state"].id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
