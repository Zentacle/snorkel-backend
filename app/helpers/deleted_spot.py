def deleted_spot_response(spot):
    """API response for a deleted spot: 404, plus the surviving spot's URL
    when it was merged, so the frontend can 301 there."""
    body = {"code": 404, "name": "Not Found", "msg": "This dive site has been removed"}
    surviving = spot.get_surviving_spot()
    if surviving:
        body["redirect_url"] = surviving.get_url()
    return body, 404
