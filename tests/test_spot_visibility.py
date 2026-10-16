"""Deleted spots 404 (or point at the spot they were merged into), and private
reviews are only visible to their author."""

import pytest
from flask_jwt_extended import create_access_token

from app.models import Review, Spot, User


@pytest.fixture
def spots(db_session):
    live = Spot(name="Refugio State Beach", is_verified=True, is_deleted=False)
    removed = Spot(name="Spam", is_verified=False, is_deleted=True)
    db_session.add_all([live, removed])
    db_session.commit()
    merged = Spot(name="Refugio", is_verified=True, is_deleted=True, merged_into_id=live.id)
    db_session.add(merged)
    db_session.commit()
    return {"live": live, "removed": removed, "merged": merged}


@pytest.mark.parametrize("path", ["/spot/{id}", "/spots/get?beach_id={id}"])
def test_deleted_spot_is_404(client, spots, path):
    response = client.get(path.format(id=spots["removed"].id))
    assert response.status_code == 404
    assert "redirect_url" not in response.get_json()


@pytest.mark.parametrize("path", ["/spot/{id}", "/spots/get?beach_id={id}"])
def test_merged_spot_points_at_surviving_spot(client, spots, path):
    response = client.get(path.format(id=spots["merged"].id))
    assert response.status_code == 404
    assert response.get_json()["redirect_url"] == f"/Beach/{spots['live'].id}/refugio-state-beach"


def test_live_spot_still_served(client, spots):
    response = client.get(f"/spot/{spots['live'].id}")
    assert response.status_code == 200
    assert response.get_json()["data"]["name"] == "Refugio State Beach"


def test_merge_chain_is_followed_and_dead_ends_are_not(db_session, spots):
    second_hop = Spot(name="Old Refugio", is_verified=True, is_deleted=True, merged_into_id=spots["merged"].id)
    into_deleted = Spot(name="Orphan", is_verified=True, is_deleted=True, merged_into_id=spots["removed"].id)
    db_session.add_all([second_hop, into_deleted])
    db_session.commit()
    assert second_hop.get_surviving_spot() == spots["live"]
    assert into_deleted.get_surviving_spot() is None
    assert spots["live"].get_surviving_spot() is None


def test_merge_endpoint_records_surviving_spot(client, db_session, spots):
    dupe = Spot(name="Refugio dupe", is_verified=True, is_deleted=False)
    db_session.add(dupe)
    db_session.commit()
    response = client.post("/spots/merge", json={"orig_id": spots["live"].id, "dupe_id": dupe.id})
    assert response.status_code == 200
    assert dupe.is_deleted is True
    assert dupe.merged_into_id == spots["live"].id


# --- private reviews


@pytest.fixture
def reviews(db_session, sample_user, spots):
    other = User(email="o@example.com", username="other", display_name="Other", unit="imperial")
    db_session.add(other)
    db_session.commit()
    beach_id = spots["live"].id
    public = Review(rating=5, text="Public", beach_id=beach_id, author_id=other.id)
    mine_private = Review(rating=4, text="My private log", beach_id=beach_id, author_id=sample_user.id, is_private=True)
    their_private = Review(rating=3, text="Their private log", beach_id=beach_id, author_id=other.id, is_private=True)
    db_session.add_all([public, mine_private, their_private])
    db_session.commit()
    return {"other": other, "beach_id": beach_id}


def review_texts(response):
    return sorted(review["text"] for review in response.get_json()["data"])


def test_anonymous_sees_only_public_reviews(client, reviews):
    response = client.get(f"/reviews/get?beach_id={reviews['beach_id']}")
    assert review_texts(response) == ["Public"]


def test_author_also_sees_own_private_reviews(client, reviews, auth_headers):
    response = client.get(f"/reviews/get?beach_id={reviews['beach_id']}", headers=auth_headers)
    assert review_texts(response) == ["My private log", "Public"]


def test_user_profile_hides_private_reviews_from_others(client, reviews, sample_user):
    response = client.get("/user/get?username=testuser")
    assert [r["text"] for r in response.get_json()["data"]["reviews"]] == []

    other_token = create_access_token(identity=reviews["other"].id)
    response = client.get("/user/get?username=testuser", headers={"Authorization": f"Bearer {other_token}"})
    assert response.get_json()["data"]["reviews"] == []


def test_user_profile_shows_private_reviews_to_their_author(client, reviews, auth_headers):
    response = client.get("/user/get?username=testuser", headers=auth_headers)
    assert [r["text"] for r in response.get_json()["data"]["reviews"]] == ["My private log"]


def test_logged_in_review_requests_bypass_the_shared_cache(app):
    from app.routes.reviews import _has_credentials

    with app.test_request_context("/reviews/get?beach_id=1"):
        assert _has_credentials() is False
    with app.test_request_context("/reviews/get?beach_id=1", headers={"Authorization": "Bearer x"}):
        assert _has_credentials() is True
    with app.test_request_context("/reviews/get?beach_id=1", headers={"Cookie": "access_token_cookie=x"}):
        assert _has_credentials() is True
