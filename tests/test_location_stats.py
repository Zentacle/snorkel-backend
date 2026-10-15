"""Tests for the location stats endpoint (/locality/stats)."""

from datetime import datetime

import pytest

from app.helpers.location_stats import parse_depth_ft, water_temp_f
from app.models import DiveShop, Review, ShoreDivingReview, Spot, Tag, User


@pytest.fixture
def area_spots(db_session, sample_country, sample_area_one, sample_area_two, sample_locality):
    shore = Tag(text="shore", type="Access", short_name="shore")
    boat = Tag(text="boat", type="Access", short_name="boat")
    db_session.add_all([shore, boat])

    location = dict(
        country_id=sample_country.id,
        area_one_id=sample_area_one.id,
        area_two_id=sample_area_two.id,
        locality_id=sample_locality.id,
        is_verified=True,
        is_deleted=False,
    )
    reef = Spot(name="Reef", max_depth="30 ft", difficulty="beginner", rating="4.5", num_reviews=10, **location)
    wall = Spot(name="Wall", max_depth="20m", difficulty="Advanced", rating="4.0", num_reviews=2, **location)
    cove = Spot(name="Cove", max_depth=None, difficulty=None, rating=None, num_reviews=0, **location)
    deleted = Spot(name="Gone", max_depth="500 ft", rating="1", num_reviews=50, **{**location, "is_deleted": True})
    reef.tags = [shore]
    wall.tags = [boat]
    cove.tags = [shore]
    db_session.add_all([reef, wall, cove, deleted])

    db_session.add(DiveShop(name="Shop", country_id=sample_country.id, locality_id=sample_locality.id))
    db_session.commit()
    return {"reef": reef, "wall": wall, "cove": cove, "deleted": deleted}


def add_review(db_session, spot, author, month, **fields):
    review = Review(
        rating=5,
        text="Nice",
        beach_id=spot.id,
        author_id=author.id,
        date_dived=datetime(2025, month, 15),
        **fields,
    )
    db_session.add(review)
    db_session.commit()
    return review


@pytest.fixture
def metric_user(db_session):
    user = User(email="m@example.com", username="metric", display_name="Metric", unit="metric")
    db_session.add(user)
    db_session.commit()
    return user


def get_stats(client, **params):
    params.setdefault("country", "us")
    return client.get("/locality/stats", query_string=params)


def test_parse_depth_ft():
    assert parse_depth_ft("49.2 ft") == 49.2
    assert parse_depth_ft("15ft") == 15
    assert parse_depth_ft("10m") == pytest.approx(32.8, abs=0.1)
    assert parse_depth_ft("30m - open end") == pytest.approx(98.4, abs=0.1)
    assert parse_depth_ft("") is None
    assert parse_depth_ft("deep") is None


def test_water_temp_uses_author_units_and_drops_implausible_values():
    assert water_temp_f(77, "imperial") == 77
    assert water_temp_f(25, "metric") == 77
    assert water_temp_f(14, "imperial") is None  # Celsius entered under imperial
    assert water_temp_f(300, "metric") is None
    assert water_temp_f(None, "imperial") is None


def test_requires_country(client):
    assert client.get("/locality/stats").status_code == 400


def test_unknown_area_is_404(client, sample_country):
    assert get_stats(client, area_one="nowhere").status_code == 404


def test_counts_and_depths_for_locality(client, area_spots, sample_user):
    response = get_stats(client, area_one="ca", area_two="la", locality="santa-monica")
    assert response.status_code == 200
    data = response.get_json()["data"]

    assert data["area"]["name"] == "Santa Monica"
    assert data["area"]["level"] == "locality"
    assert data["num_spots"] == 3  # deleted spot excluded
    assert data["num_shops"] == 1
    assert data["access"] == {"shore": 2, "boat": 1}
    assert data["difficulty"] == {"beginner": 1, "advanced": 1, "unrated": 1}
    assert data["max_depth_ft"]["min"] == 30
    assert data["max_depth_ft"]["max"] == pytest.approx(65.6, abs=0.1)
    assert data["max_depth_ft"]["num_spots"] == 2
    assert data["num_reviews"] == 12
    assert data["average_rating"] == pytest.approx((4.5 * 10 + 4.0 * 2) / 12, abs=0.01)
    assert [spot["name"] for spot in data["top_spots"]] == ["Reef", "Wall"]


def test_same_stats_at_country_level(client, area_spots):
    data = get_stats(client).get_json()["data"]
    assert data["area"]["level"] == "country"
    assert data["num_spots"] == 3


def test_sparse_review_data_is_null(client, db_session, area_spots, sample_user):
    add_review(db_session, area_spots["reef"], sample_user, 6, water_temp=78)
    data = get_stats(client).get_json()["data"]
    assert data["water_temp"] is None  # only 1 report
    assert data["visibility"] is None
    assert data["seasonality"] is None  # fewer than 12 dated dives
    assert data["ratings_breakdown"] is None


def test_review_aggregates(client, db_session, area_spots, sample_user, metric_user):
    reef = area_spots["reef"]
    for month in (6, 6, 7, 7, 7, 8):
        add_review(db_session, reef, sample_user, month, visibility=4, water_temp=78)
    for month in (1, 2, 3, 4, 5):
        add_review(db_session, reef, metric_user, month, visibility=2, water_temp=24)
    # stray visibility in feet and a Celsius value entered under imperial: ignored
    add_review(db_session, reef, sample_user, 7, visibility=40, water_temp=14)

    data = get_stats(client).get_json()["data"]

    seasonality = data["seasonality"]
    assert seasonality["num_dives"] == 12
    assert seasonality["busiest_months"] == [6, 7]  # Jan-May and Aug have 1 dive each
    july = seasonality["months"][6]
    assert july["month"] == 7 and july["num_dives"] == 4
    assert july["avg_visibility"] == 4
    assert july["avg_water_temp_f"] == 78
    assert july["avg_water_temp_c"] == pytest.approx(25.6, abs=0.1)
    assert seasonality["months"][0]["avg_water_temp_f"] is None  # 1 report in January

    assert data["visibility"] == {"average": pytest.approx(3.1, abs=0.1), "scale": 5, "num_reports": 11}
    water = data["water_temp"]
    assert water["num_reports"] == 11
    assert water["min_f"] == pytest.approx(75.2, abs=0.1)
    assert water["max_f"] == 78


def test_shorediving_ratings_breakdown(client, db_session, area_spots, sample_user):
    for reef_rating in (5, 4, 3):
        review = add_review(db_session, area_spots["reef"], sample_user, 6)
        db_session.add(ShoreDivingReview(review_id=review.id, reef=reef_rating, crowds=0))
    db_session.commit()

    breakdown = get_stats(client).get_json()["data"]["ratings_breakdown"]
    assert breakdown == {"reef": {"average": 4, "num_ratings": 3}}  # crowds=0 means unrated


def test_spots_get_still_returns_area(client, area_spots):
    """/spots/get now uses the shared area lookup."""
    response = client.get("/spots/get", query_string={"country": "us", "area_one": "ca", "limit": "none"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["area"]["name"] == "California"
    assert {spot["name"] for spot in body["data"]} == {"Reef", "Wall", "Cove"}
    assert client.get("/spots/get", query_string={"country": "us", "area_one": "nope"}).status_code == 404
