import os
import time

import requests

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def _most_specific_with_country(results):
    """Address components of the first (most specific) result that includes a
    country. At sea, Google's first result is often only a plus code (a grid
    reference with no country), followed by e.g. just the country."""
    for result in results:
        components = result.get("address_components", [])
        if any("country" in component.get("types", []) for component in components):
            return components
    return None


def reverse_geocode(latitude, longitude, retries=3):
    """Google reverse geocoding. Returns (status, address_components).

    language=en keeps place names in Latin script; without it Google can
    answer in the local script, which produced empty URL slugs.
    """
    for attempt in range(retries):
        response = requests.get(
            GEOCODE_URL,
            params={
                "latlng": f"{latitude},{longitude}",
                "key": os.environ.get("GOOGLE_API_KEY"),
                "language": "en",
            },
            timeout=10,
        ).json()
        status = response.get("status")
        if status == "OVER_QUERY_LIMIT" and attempt < retries - 1:
            time.sleep(2**attempt)
            continue
        if status == "OK":
            return status, _most_specific_with_country(response["results"])
        return status, None
    return "OVER_QUERY_LIMIT", None
