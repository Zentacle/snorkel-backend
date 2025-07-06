import os

from amplitude import Amplitude, BaseEvent
from flask.helpers import make_response
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    set_access_cookies,
    set_refresh_cookies,
)


def login(user):
    auth_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    if auth_token:
        responseObject = {
            "data": {
                "type": "login",
                "status": "success",
                "message": "Successfully logged in.",
                "auth_token": auth_token,
                "refresh_token": refresh_token,
            },
            "user": user.get_dict(),
        }
        client = Amplitude(os.environ.get("AMPLITUDE_API_KEY"))
        user_id = user.id
        client.configuration.min_id_length = 1
        event = BaseEvent(event_type="login_success", user_id=f"{user_id}")
        client.track(event)

        resp = make_response(responseObject)
        set_access_cookies(resp, auth_token)
        set_refresh_cookies(resp, refresh_token)
        return resp
