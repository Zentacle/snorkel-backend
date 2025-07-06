from app.models import DiveShop


def typeahead_from_spot(spot):
    return {
        "id": spot.id,
        "text": spot.name,
        "url": spot.get_url(),
        "type": "site",
        "subtext": spot.location_city,
        "data": {
            "latitude": spot.latitude,
            "longitude": spot.longitude,
            "location_city": spot.location_city,
        },
    }


def typeahead_from_shop(shop):
    return {
        "id": shop.id,
        "text": shop.name,
        "url": DiveShop.get_url(shop),
        "type": "shop",
        "subtext": shop.city,
        "data": {
            "latitude": shop.latitude,
            "longitude": shop.longitude,
            "location_city": shop.city,
        },
    }
