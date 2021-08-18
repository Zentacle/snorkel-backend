from app.models import *
from flask_jwt_extended import *
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from flask.helpers import make_response
import os
import bcrypt
import re

def demicrosoft(fn):
    fn = re.sub("[^0-9a-zA-Z ]+", "", fn)
    for ch in [' ']:
        fn = fn.replace(ch,"-")
    return fn

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

  if not email:
    return { 'msg': 'Please enter an email' }, 400
  if not first_name:
    return { 'msg': 'Please enter a name' }, 400

  user = User.query.filter_by(email=email).first()
  if user:
    return { 'msg': 'An account with this email already exists' }, 400
  if username:
    user = User.query.filter_by(username=username).first()
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
    'auth_token': auth_token
  }
  resp = make_response(responseObject)
  set_access_cookies(resp, auth_token)
  set_refresh_cookies(resp, refresh_token)
  if not password:
    message = Mail(
      from_email=('no-reply@zentacle.com', 'Zentacle'),
      to_emails=email)
    message.reply_to = 'mjmayank@gmail.com'

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
  message = Mail(
      from_email=('no-reply@zentacle.com', 'Zentacle'),
      to_emails='mjmayank@gmail.com')

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

def login(user):
  auth_token = create_access_token(identity=user.id)
  refresh_token = create_refresh_token(identity=user.id)
  if auth_token:
    responseObject = {
      'data': {
        'status': 'success',
        'message': 'Successfully logged in.',
        'auth_token': auth_token
      },
      'user': user.get_dict()
    }
    resp = make_response(responseObject)
    set_access_cookies(resp, auth_token)
    set_refresh_cookies(resp, refresh_token)
    return resp

def get_localities(address_components):
  locality_name = None
  area_1_name = None
  area_2_name = None
  country_name = None
  for component in address_components:
    if 'locality' in component.get('types'):
      locality_name = component.get('long_name')
    if 'administrative_area_level_1' in component.get('types'):
      area_1_name = component.get('long_name')
      area_1_short_name = demicrosoft(component.get('short_name').lower())
    if 'administrative_area_level_2' in component.get('types'):
      area_2_name = component.get('long_name')
      area_2_short_name = demicrosoft(component.get('short_name').lower())
    if 'country' in component.get('types'):
      country_name = component.get('long_name')
      country_short_name = demicrosoft(component.get('short_name').lower())
  country = Country.query.filter_by(name=country_name).first()
  if not country:
    country = Country(
      name=country_name,
      short_name=country_short_name,
    )
  area_1 = AreaOne.query.filter_by(name=area_1_name).first()
  if not area_1:
    area_1 = AreaOne(
      name=area_1_name,
      country=country,
      short_name=area_1_short_name,
    )
  area_2 = AreaTwo.query.filter_by(google_name=area_2_name).first()
  if not area_2:
    area_2 = AreaTwo(
      google_name=area_2_name,
      name=area_2_name,
      area_one=area_1,
      country=country,
      short_name=area_2_short_name,
    )
  locality = Locality.query.filter_by(name=locality_name).first()
  if not locality:
    locality = Locality(
      name=locality_name,
      area_one=area_1,
      area_two=area_2,
      country=country,
    )
  return (locality, area_2, area_1, country)