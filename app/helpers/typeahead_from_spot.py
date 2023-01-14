def typeahead_from_spot(spot):
    return {
        'id': spot.id,
        'text': spot.name,
        'url': spot.get_url(),
        'type': 'site',
        'subtext': spot.location_city,
        'data': {
            'latitude': spot.latitude,
            'longitude': spot.longitude,
            'location_city': spot.location_city,
        }
    }
