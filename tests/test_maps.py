"""Static map endpoint: optional zoom and marker, backwards-compatible caching."""

import pytest

from app.routes import maps


@pytest.fixture
def google(monkeypatch):
    calls = []

    class Response:
        content = b"PNG"

        def raise_for_status(self):
            pass

    def fake_get(url, params, timeout):
        calls.append(params)
        return Response()

    monkeypatch.setenv("GOOGLE_API_KEY", "key")
    monkeypatch.setattr(maps.requests, "get", fake_get)
    monkeypatch.setattr(maps, "check_s3_map_exists", lambda key: False)
    monkeypatch.setattr(maps, "upload_map_to_s3", lambda data, key: True)
    return calls


def test_default_request_is_unchanged(client, google):
    response = client.get("/maps/static?latitude=21.6&longitude=-158.06")
    assert response.status_code == 200
    params = google[0]
    assert params["markers"] == "color:blue|label:1|21.6,-158.06"
    assert "zoom" not in params and "center" not in params


def test_zoom_without_marker(client, google):
    response = client.get("/maps/static?latitude=21.6&longitude=-158.06&zoom=10&marker=0&size=640x320")
    assert response.status_code == 200
    params = google[0]
    assert "markers" not in params
    assert params["center"] == "21.6,-158.06"
    assert params["zoom"] == 10
    assert params["size"] == "640x320"


def test_invalid_zoom(client, google):
    assert client.get("/maps/static?latitude=1&longitude=1&zoom=30").status_code == 400


def test_cache_key_is_backwards_compatible():
    assert maps.generate_map_key(1, 2) == maps.generate_map_key(1, 2, zoom=None, marker=True)
    assert maps.generate_map_key(1, 2) != maps.generate_map_key(1, 2, zoom=10, marker=False)
    assert maps.generate_map_key(1, 2, zoom=10, marker=False) != maps.generate_map_key(1, 2, zoom=11, marker=False)
