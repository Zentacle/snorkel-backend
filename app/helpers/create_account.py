from app.models import *
from amplitude import Amplitude, BaseEvent
from flask_jwt_extended import create_access_token, create_refresh_token, set_access_cookies, set_refresh_cookies
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from flask.helpers import make_response
from sqlalchemy import func
from app.helpers.validate_email_format import validate_email_format
import os
import bcrypt
import newrelic

def create_account(
  db,
  first_name=None,
  last_name=None,
  display_name=None,
  email=None,
  profile_pic=None,
  username=None,
  unencrypted_password=None,
  app_name=None,
):
  password = bcrypt.hashpw(unencrypted_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') \
    if unencrypted_password \
    else None

  if not validate_email_format(email):
    return { 'msg': 'Please enter a valid email' }, 401
  if not email:
    newrelic.agent.notice_error()
    return { 'msg': 'Please enter an email' }, 422
  if not first_name:
    newrelic.agent.notice_error()
    return { 'msg': 'Please enter a name' }, 422

  email = email.lower()
  user = User.query.filter(func.lower(User.email)==email).first()
  if user:
    return { 'msg': 'An account with this email already exists' }, 409
  if username:
    username = username.lower()
    if not username.isalnum():
      return { 'msg': 'Usernames can\'t have special characters' }, 422
    user = User.query.filter(func.lower(User.username)==username).first()
    if user:
      newrelic.agent.notice_error()
      return { 'msg': 'An account with this username already exists' }, 409
  user = User(
    first_name=first_name,
    last_name=last_name,
    display_name=display_name,
    email=email,
    password=password,
    username=username,
    profile_pic=profile_pic
  )
  db.session.add(user)
  db.session.commit()

  client = Amplitude(os.environ.get('AMPLITUDE_API_KEY'))
  user_id=user.id
  client.configuration.min_id_length = 1
  event = BaseEvent(event_type="register_success", user_id=f'{user_id}', event_properties={ 'app': app_name })
  client.track(event)

  auth_token = create_access_token(identity=user.id)
  refresh_token = create_refresh_token(identity=user.id)
  responseObject = {
    'data': {
      'type': 'register',
      'status': 'success',
      'message': 'Successfully registered.',
      'auth_token': auth_token,
      'refresh_token': refresh_token,
    },
    'user': user.get_dict(),
  }
  resp = make_response(responseObject)
  set_access_cookies(resp, auth_token)
  set_refresh_cookies(resp, refresh_token)

  message = Mail(
    from_email=('hello@zentacle.com', 'Zentacle'),
    to_emails=email)
  message.reply_to = 'mayank@zentacle.com'

  message.template_id = 'd-9aeec0123b324082b53095ce06987e27'
  message.dynamic_template_data = {
      'first_name': first_name
  }
  try:
      sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
      sg.send(message)
  except Exception as e:
      print(e.body)
  message = Mail(
      from_email=('hello@zentacle.com', 'Zentacle'),
      to_emails='mayank@zentacle.com')

  message.template_id = 'd-926fe53d5696480fb65b92af8cd8484e'
  message.dynamic_template_data = {
      'first_name': display_name,
      'email': email,
      'app': app_name,
  }
  if not os.environ.get('FLASK_ENV') == 'development':
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        print(e.body)
  data = {
    "contacts": [
        {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        }
    ],
    "list_ids": ['49e5fa45-3112-4a99-ba4b-9e5a8d18af3c']
  }

  try:
    response = sg.client.marketing.contacts.put(
        request_body=data
    )
  except Exception as e:
    print(e.body)
  return resp