from app.models import *
from flask_jwt_extended import create_access_token, create_refresh_token, set_access_cookies, set_refresh_cookies
from flask.helpers import make_response

def login(user):
  auth_token = create_access_token(identity=user.id)
  refresh_token = create_refresh_token(identity=user.id)
  if auth_token:
    responseObject = {
      'data': {
        'type': 'login',
        'status': 'success',
        'message': 'Successfully logged in.',
        'auth_token': auth_token,
        'refresh_token': refresh_token
      },
      'user': user.get_dict()
    }
    resp = make_response(responseObject)
    set_access_cookies(resp, auth_token)
    set_refresh_cookies(resp, refresh_token)
    return resp
