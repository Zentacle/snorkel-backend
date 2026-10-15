"""Tests for the dive shop edit endpoint."""

import pytest

from app.models import DiveShop


@pytest.fixture
def owned_shop(db_session, sample_user):
    shop = DiveShop(
        name="Scuba Evolution",
        padi_store_id="27051",
        address1="31 Vallot Street",
        city="Johannesburg",
        phone="+27 11 000 0000",
        owner_user_id=sample_user.id,
        hours=[{"shopDayName": "Monday", "shopHourOpen": "08:00", "shopHourClose": "17:00"}],
        padi_data={
            "rentals": ["BCD", "Regulator"],
            "features": ["Equipment Rentals"],
            "images": ["https://diveshopmedia.padiww.com/a.jpg"],
        },
    )
    db_session.add(shop)
    db_session.commit()
    return shop


def patch(client, shop, body, headers):
    return client.patch(f"/shop/patch/{shop.id}", json=body, headers=headers)


def test_owner_can_update_full_shop_details(client, owned_shop, auth_headers):
    body = {
        "id": owned_shop.id,
        "address1": "Shop U44, Glenvista Shopping Centre",
        "address2": "Biggarsberg St, Glenvista",
        "city": "Johannesburg South",
        "zip": "2190",
        "phone": "+27 10 335 1000",
        "email": "shop@scubaevolution.co.za",
        "website": "https://scubaevolution.co.za/",
        "latitude": "-26.28",
        "hours": [
            {"shopDayName": "saturday", "shopHourOpen": "09:00", "shopHourClose": "16:00"},
            {"shopDayName": "Monday", "shopHourOpen": "09:00", "shopHourClose": "17:00"},
        ],
        "padi_data": {"rentals": [], "features": ["Nitrox"]},
    }
    resp = patch(client, owned_shop, body, auth_headers)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()["data"]
    assert data["full_address"].startswith("Shop U44, Glenvista Shopping Centre")
    assert data["latitude"] == -26.28
    assert [h["shopDayName"] for h in data["hours"]] == ["Monday", "Saturday"]
    assert data["padi_data"]["rentals"] == []
    assert data["padi_data"]["features"] == ["Nitrox"]
    # keys not sent are preserved
    assert data["padi_data"]["images"] == ["https://diveshopmedia.padiww.com/a.jpg"]


def test_blank_strings_clear_fields(client, owned_shop, auth_headers):
    resp = patch(client, owned_shop, {"address2": "  ", "hours": []}, auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["address2"] is None
    assert data["hours"] is None


def test_unknown_fields_rejected(client, owned_shop, auth_headers):
    resp = patch(client, owned_shop, {"rating": 5}, auth_headers)
    assert resp.status_code == 400


def test_admin_fields_require_admin(client, owned_shop, auth_headers):
    assert patch(client, owned_shop, {"padi_store_id": "1"}, auth_headers).status_code == 403


def test_admin_can_set_padi_store_id(client, owned_shop, admin_auth_headers):
    resp = patch(client, owned_shop, {"padi_store_id": "99999"}, admin_auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["padi_store_id"] == "99999"


@pytest.mark.parametrize(
    "hours",
    [
        "Mon-Fri 9-5",
        [{"shopDayName": "Funday", "shopHourOpen": "09:00", "shopHourClose": "17:00"}],
        [{"shopDayName": "Monday", "shopHourOpen": "9am", "shopHourClose": "17:00"}],
    ],
)
def test_invalid_hours_rejected(client, owned_shop, auth_headers, hours):
    resp = patch(client, owned_shop, {"hours": hours}, auth_headers)
    assert resp.status_code == 400


def test_invalid_padi_data_rejected(client, owned_shop, auth_headers):
    assert patch(client, owned_shop, {"padi_data": {"images": []}}, auth_headers).status_code == 400
    assert patch(client, owned_shop, {"padi_data": {"padiRating": "x"}}, auth_headers).status_code == 400
    assert patch(client, owned_shop, {"padi_data": {"rentals": "BCD"}}, auth_headers).status_code == 400


def test_non_owner_forbidden(client, db_session, owned_shop, admin_user, auth_headers):
    owned_shop.owner_user_id = admin_user.id
    db_session.commit()
    resp = patch(client, owned_shop, {"name": "Hijacked"}, auth_headers)
    assert resp.status_code == 403
