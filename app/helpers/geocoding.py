import os
import time

import requests

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


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
            return status, response["results"][0].get("address_components", [])
        return status, None
    return "OVER_QUERY_LIMIT", None
