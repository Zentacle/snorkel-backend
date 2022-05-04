from app.models import *
from flask_jwt_extended import create_access_token, create_refresh_token, set_access_cookies, set_refresh_cookies
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from flask.helpers import make_response
from sqlalchemy import func
from app.helpers.validate_email_format import validate_email_format
import os
import bcrypt

def create_account(
  db,
  first_name=None,
  last_name=None,
  display_name=None,
  email=None,
  profile_pic=None,
  username=None,
  unencrypted_password=None,
):
  password = bcrypt.hashpw(unencrypted_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') \
    if unencrypted_password \
    else None

  if not validate_email_format(email):
    return { 'msg': 'Please enter a valid email' }, 401
  if not email:
    return { 'msg': 'Please enter an email' }, 400
  if not first_name:
    return { 'msg': 'Please enter a name' }, 400

  user = User.query.filter_by(email=email).first()
  if user:
    return { 'msg': 'An account with this email already exists' }, 400
  if username:
    username = username.lower()
    user = User.query.filter(func.lower(User.username)==username).first()
    if user:
      return { 'msg': 'An account with this username already exists' }, 400
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
  auth_token = create_access_token(identity=user.id)
  refresh_token = create_refresh_token(identity=user.id)
  responseObject = {
    'status': 'success',
    'message': 'Successfully registered.',
    'auth_token': auth_token,
    'refresh_token': refresh_token
  }
  resp = make_response(responseObject)
  set_access_cookies(resp, auth_token)
  set_refresh_cookies(resp, refresh_token)
  if not password:
    message = Mail(
      from_email=('hello@zentacle.com', 'Zentacle'),
      to_emails=email)
    message.reply_to = 'mayank@zentacle.com'

    message.template_id = 'd-b683fb33f315435e8d2177def8e57d6f'
    message.dynamic_template_data = {
        'first_name': first_name,
        'url': 'https://www.zentacle.com/setpassword?userid='+str(user.id)
    }
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        print(e.body)
  else:
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
      'first_name': first_name,
      'email': email,
  }
  if not os.environ.get('FLASK_ENV') == 'development':
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        print(e.body)
  return resp