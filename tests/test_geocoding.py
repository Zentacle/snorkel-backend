"""reverse_geocode picks the most specific result that has a country."""

from app.helpers import geocoding


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def respond(monkeypatch, body):
    monkeypatch.setattr(geocoding.requests, "get", lambda *args, **kwargs: FakeResponse(body))


PLUS_CODE = {"types": ["plus_code"], "address_components": [{"long_name": "8CPW9CQ9+4Q", "types": ["plus_code"]}]}
FRANCE = {"types": ["country"], "address_components": [{"long_name": "France", "types": ["country", "political"]}]}
TOWN = {
    "types": ["locality"],
    "address_components": [
        {"long_name": "Arcachon", "types": ["locality"]},
        {"long_name": "France", "types": ["country", "political"]},
    ],
}


def test_skips_plus_code_results_at_sea(monkeypatch):
    # actual response for an offshore wreck in the Bay of Biscay
    respond(monkeypatch, {"status": "OK", "results": [PLUS_CODE, FRANCE]})
    status, components = geocoding.reverse_geocode(44.38778, -1.58055)
    assert status == "OK"
    assert [c["long_name"] for c in components] == ["France"]


def test_prefers_the_most_specific_result(monkeypatch):
    respond(monkeypatch, {"status": "OK", "results": [PLUS_CODE, TOWN, FRANCE]})
    _, components = geocoding.reverse_geocode(44.66, -1.17)
    assert components[0]["long_name"] == "Arcachon"


def test_no_result_with_a_country(monkeypatch):
    respond(monkeypatch, {"status": "OK", "results": [PLUS_CODE]})
    assert geocoding.reverse_geocode(0, -30) == ("OK", None)
