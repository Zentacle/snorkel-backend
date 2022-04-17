from __future__ import print_function
from flask import Flask, request, jsonify
from flask.helpers import make_response
from flask_cors import CORS
import io
import os
import os.path
import logging

from app.models import *
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_, not_, func, sql
import bcrypt
from flask_jwt_extended import *
from datetime import timezone, timedelta
from flask_migrate import Migrate
import dateutil.parser
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import logging
import boto3
from botocore.exceptions import ClientError
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.helpers.create_account import create_account
from app.helpers.login import login
from app.helpers.get_localities import get_localities
from app.helpers.validate_email_format import validate_email_format
import requests
from sqlalchemy.exc import OperationalError
from app.scripts.openapi import spec

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
SQLALCHEMY_DATABASE_URI = (os.environ.get('DATABASE_URL').replace("://", "ql://", 1)
  if not os.environ.get('FLASK_ENV') == 'development'
  else os.environ.get('DATABASE_URL'))
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = "super-secret"  # Change this!
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
app.config["JWT_TOKEN_LOCATION"] = ["cookies", "headers"]
app.config["JWT_SESSION_COOKIE"] = False
if __name__ != '__main__':
  gunicorn_logger = logging.getLogger('gunicorn.error')
  app.logger.handlers = gunicorn_logger.handlers
  app.logger.setLevel(gunicorn_logger.level)
  # logging.basicConfig()
  # logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
app.config["JWT_COOKIE_SECURE"] = (True
  if not os.environ.get('FLASK_ENV') == 'development'
  else False
)

cors = CORS(app)
jwt = JWTManager(app)
db.init_app(app)
migrate = Migrate(compare_type=True)
migrate.init_app(app, db)

# Register a callback function that loades a user from your database whenever
# a protected route is accessed. This should return any python object on a
# successful lookup, or None if the lookup failed for any reason (for example
# if the user has been deleted from the database).
@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    user_id = jwt_data["sub"]
    return User.query.filter_by(id=user_id).one_or_none()

# Using an `after_request` callback, we refresh any token that is within 30
# minutes of expiring. Change the timedeltas to match the needs of your application.
@app.after_request
def refresh_expiring_jwts(response):
    try:
        exp_timestamp = get_jwt()["exp"]
        now = datetime.now(timezone.utc)
        target_timestamp = datetime.timestamp(now + timedelta(minutes=30))
        if target_timestamp > exp_timestamp:
            access_token = create_access_token(identity=get_jwt_identity())
            set_access_cookies(response, access_token)
        return response
    except (RuntimeError, KeyError):
        # Case where there is not a valid JWT. Just return the original respone
        return response

@app.route("/")
def home_view():
  return "Hello world"

@app.route("/db")
def db_create():
  db.create_all()
  return "<h1>Welcome to Zentacle</h1>"

@app.route("/delete")
def delete():
  email = request.args.get('email')
  user = User.query.filter_by(email=email).first()
  db.session.delete(user)
  db.session.commit()
  return "Successfully deleted user: " + email

@app.route("/getall/email")
@jwt_required()
def get_emails():
  if not get_current_user().admin:
    return "Not allowed", 401
  users = User.query \
    .filter(
      and_(
        not_(User.email.contains('zentacle.com')),
        User.is_fake.is_not(True)
      )
    )
  output = []
  for user in users:
    data = {
      "email": user.email,
      "first_name": user.first_name,
      "display_name": user.display_name,
      "id": user.id,
    }
    output.append(data)
  return { 'data': output }

@app.route("/getall")
def getAllData():
    users = None
    if request.args.get('top'):
      users = db.session.query(
          User,
          db.func.count(User.reviews).label('num_reviews')
        ) \
        .join(Review) \
        .group_by(User) \
        .order_by(db.text('num_reviews DESC')) \
        .limit(10)
    elif request.args.get('real'):
      users = User.query \
        .filter(
          and_(
            not_(User.email.contains('zentacle.com')),
            User.is_fake.is_not(True),
            User.email.is_not(None)
          )
        )
      output = []
      for user in users:
        data = user.get_dict()
        output.append(data)
      return { 'data': output, 'count': len(output) }
    else:
      users = db.session.query(
          User,
          db.func.count(User.reviews).label('num_reviews')
        ) \
        .join(Review) \
        .group_by(User) \
        .all()
    output = []
    for user, num_reviews in users:
      data = user.get_dict()
      data['num_reviews'] = num_reviews
      output.append(data)
    return { 'data': output }

"""
  ?email=mjmayank@gmail.com
"""
@app.route('/test', methods=["GET"])
def get_user_test():
  email = request.args.get('email')
  users = User.query.filter_by(email=email).all()
  output = []
  for user in users:
    output.append({
      'email': user.email,
      'password': user.password,
    })
  return { 'data': output }

"""
Auth data goes in a cookie
"""
@app.route("/user/register", methods=["POST"])
def user_signup():
  """ Register
  ---
  post:
      summary: Register new user endpoint.
      description: Register a new user
      parameters:
          - name: first_name
            in: body
            description: First Name
            type: string
            required: true
          - name: last_name
            in: body
            description: Last Name
            type: string
            required: true
          - name: email
            in: body
            description: Email address
            type: string
            required: true
          - name: username
            in: body
            description: Username
            type: string
            required: false
          - name: profile_pic
            in: body
            description: Profile Pic
            type: string
            required: false
          - name: password
            in: body
            description: Password
            type: string
            required: false
      responses:
          200:
              description: Returns User object
              content:
                application/json:
                  schema: UserSchema
          400:
              content:
                application/json:
                  schema:
                    msg: string
              description: User couldn't be created.
  """
  first_name = request.json.get('first_name') or ''
  last_name = request.json.get('last_name') or ''
  email = request.json.get('email')
  username = request.json.get('username')
  profile_pic = request.json.get('profile_pic')
  unencrypted_password = request.json.get('password')
  display_name = first_name + ' ' + last_name

  resp = create_account(
    db,
    first_name=first_name,
    last_name=last_name,
    display_name=display_name,
    email=email,
    profile_pic=profile_pic,
    username=username,
    unencrypted_password=unencrypted_password,
  )
  return resp

@app.route("/user/google_register", methods=["POST"])
def user_google_signup():
  """ Google Register
  ---
  post:
      summary: Register new user with Google auth endpoint.
      description: Register a new user with Google auth
      parameters:
          - name: credential
            in: body
            description: google oauth token credential returned from Google login button
            type: string
            required: true
      responses:
          200:
              description: Returns User object
              content:
                application/json:
                  schema: UserSchema
          400:
              content:
                application/json:
                  schema:
                    msg: string
              description: User couldn't be created.
  """
  token = request.json.get('credential')
  app.logger.error(request.json.get('credential'))
  userid = None
  try:
    # Specify the CLIENT_ID of the app that accesses the backend:
    idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), os.environ.get('GOOGLE_CLIENT_ID'))

    # Or, if multiple clients access the backend server:
    # idinfo = id_token.verify_oauth2_token(token, requests.Request())
    # if idinfo['aud'] not in [CLIENT_ID_1, CLIENT_ID_2, CLIENT_ID_3]:
    #     raise ValueError('Could not verify audience.')

    # If auth request is from a G Suite domain:
    # if idinfo['hd'] != GSUITE_DOMAIN_NAME:
    #     raise ValueError('Wrong hosted domain.')

    # ID token is valid. Get the user's Google Account ID from the decoded token.
    email = idinfo.get('email')
    user = User.query.filter_by(email=email).first()
    if user:
      return login(user)
    first_name = idinfo.get('given_name')
    last_name = idinfo.get('last_name')
    display_name = idinfo.get('name')
    profile_pic = idinfo.get('picture')
    resp = create_account(
      db,
      first_name,
      last_name,
      display_name,
      email,
      profile_pic,
    )
    return resp
  except ValueError:
    return { 'data': token }, 401
    # Invalid token
    pass
  return { 'data': userid, 'token': token }

@app.route("/user/register/password", methods=["POST"])
def user_finish_signup():
  """ Add account password
  ---
  post:
      summary: Add password for a newly registered user. Can't be used to change password.
      description: Add password for a newly registered user. Can't be used to change password.
      parameters:
          - name: user_id
            in: body
            description: User ID (not username)
            type: string
            required: true
          - name: password
            in: body
            description: password
            type: string
            required: true
      responses:
          200:
              description: Returns User object
              content:
                application/json:
                  schema: UserSchema
          400:
              content:
                application/json:
                  schema:
                    Error:
                      properties:
                        msg:
                          type: string
              description: User couldn't be created.
  """
  user_id = request.json.get('user_id')
  user = User.query.filter_by(id=user_id).first()
  if user.password:
    return { 'msg': 'This user has already registered a password' }, 401
  unencrypted_password = request.json.get('password')
  password = bcrypt.hashpw(unencrypted_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
  user.password = password
  db.session.commit()
  auth_token = create_access_token(identity=user.id)
  refresh_token = create_refresh_token(identity=user.id)
  responseObject = {
    'status': 'success',
    'message': 'Successfully registered.',
    'auth_token': auth_token,
    'username': user.username,
  }
  resp = make_response(responseObject)
  set_access_cookies(resp, auth_token)
  set_refresh_cookies(resp, refresh_token)
  return resp

"""
Save the response token as an Authorization header with the format
Authorization: Bearer <token>
"""
@app.route("/user/login", methods=["POST"])
def user_login():
  """ Login
  ---
  post:
      summary: login with username/email and password
      description: login with username/email and password
      parameters:
          - name: email
            in: body
            description: username or password
            type: string
            required: true
          - name: password
            in: body
            description: password
            type: string
            required: true
      responses:
          200:
              description: Returns User object
              content:
                application/json:
                  schema: UserSchema
          400:
              content:
                application/json:
                  schema:
                    Error:
                      properties:
                        msg:
                          type: string
              description: Wrong password.
  """
  email = request.json.get('email')
  password = request.json.get('password')
  
  user = User.query.filter(or_(User.email==email, User.username==email)).first()
  if not user:
    return { 'msg': 'Wrong password or user does not exist' }, 400
  if bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
    return login(user)
  else:
    return { 'msg': 'Wrong password or user does not exist' }, 400

@app.route("/user/patch", methods=["PATCH"])
@jwt_required()
def patch_user():
  """ Patch User
    ---
    patch:
        summary: patch user (admin only)
        description: patch user (admin only). also include the params of the user that you want to change in the body
        parameters:
          - name: id
            in: body
            description: user id
            type: int
            required: true
        responses:
            200:
                description: Returns User object
                content:
                  application/json:
                    schema: UserSchema
            400:
                content:
                  application/json:
                    schema:
                      Error:
                        properties:
                          msg:
                            type: string
                description: Not logged in.
  """
  user = get_current_user()
  user_id = request.json.get('id')
  if user.admin and user_id:
    user = User.query.filter_by(id=user_id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      if key == 'username':
        setattr(user, key, updates.get(key).lower())
      else:
        setattr(user, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  user.id
  return user.get_dict(), 200

@app.route("/user/me")
@jwt_required(refresh=True)
def get_me():
    """ Fetch Current User
    ---
    get:
        summary: fetch current user (without reviews)
        description: fetch current user. Store auth token in header as Authorization: `Bearer ${token}`
        responses:
            200:
                description: Returns User object
                content:
                  application/json:
                    schema: UserSchema
            400:
                content:
                  application/json:
                    schema:
                      Error:
                        properties:
                          msg:
                            type: string
                description: Not logged in.
    """
    user = get_current_user()
    resp = make_response(user.get_dict())
    auth_token = create_access_token(identity=user.id)
    set_access_cookies(resp, auth_token)
    return resp

@app.route("/refresh")
@jwt_required(refresh=True)
def refresh_token():
  """ Refresh auth token
  ---
  get:
      summary: Refresh auth token
      description: Refresh auth token
      responses:
          200:
              description: Returns User object
              content:
                application/json:
                  schema: UserSchema
          400:
              content:
                application/json:
                  schema:
                    Error:
                      properties:
                        msg:
                          type: string
              description: Not logged in.
  """
  user_id = get_jwt_identity()
  auth_token = create_access_token(identity=user_id)
  return jsonify(auth_token=auth_token)

@app.route("/spots/get")
def get_spots():
  """ Get Dive Sites/Beaches
  ---
  get:
      summary: Get dive sites
      description: Get dive sites
      parameters:
          - name: beach_id
            in: body
            description: Beach ID
            type: string
            required: false
          - name: locality
            in: body
            description: locality (eg. Kihei)
            type: string
            required: false
          - name: area_two
            in: body
            description: area_two (eg. Maui)
            type: string
            required: false
          - name: area_one
            in: body
            description: area_one (eg. Hawaii)
            type: string
            required: false
          - name: country
            in: body
            description: country (eg. USA)
            type: string
            required: false
          - name: sort
            in: body
            description: sort (latest, most_reviewed, top). defaults to top
            type: string
            required: false
          - name: limit
            in: body
            description: limit on number of results returned (default 15)
            type: string
            required: false
      responses:
          200:
              description: Returns singular beach object or list of beach objects
              content:
                application/json:
                  schema: BeachSchema
          400:
              content:
                application/json:
                  schema:
                    Error:
                      properties:
                        msg:
                          type: string
              description: Wrong password.
  """
  is_shorediving = False
  area = None
  spot = None
  sd_spot = None
  if request.args.get('beach_id') or request.args.get('region') or request.args.get('sd_id'):
    if request.args.get('beach_id'):
      beach_id = request.args.get('beach_id')
      spot = Spot.query \
        .options(joinedload('locality')) \
        .options(joinedload('area_two')) \
        .options(joinedload('area_one')) \
        .options(joinedload('country')) \
        .options(joinedload('shorediving_data')) \
        .filter_by(id=beach_id) \
        .first_or_404()
      if spot.shorediving_data:
        sd_spot = spot.shorediving_data
    elif request.args.get('region'):
      is_shorediving = True
      region = request.args.get('region')
      destination = request.args.get('destination')
      site = request.args.get('site')
      sd_spot = ShoreDivingData.query \
        .options(joinedload('spot')) \
        .filter(and_(
          ShoreDivingData.region_url==region,
          ShoreDivingData.destination_url==destination,
          ShoreDivingData.name_url==site,
        )) \
        .first_or_404()
      spot = Spot.query \
        .options(joinedload('locality')) \
        .options(joinedload('area_two')) \
        .options(joinedload('area_one')) \
        .options(joinedload('country')) \
        .filter_by(id=sd_spot.spot_id) \
        .first()
    elif request.args.get('sd_id'):
      is_shorediving = True
      fsite = request.args.get('sd_id')
      sd_spot = ShoreDivingData.query \
        .options(joinedload('spot')) \
        .filter_by(id=fsite) \
        .first_or_404()
      spot = Spot.query \
        .options(joinedload('locality')) \
        .options(joinedload('area_two')) \
        .options(joinedload('area_one')) \
        .options(joinedload('country')) \
        .filter_by(id=sd_spot.spot_id) \
        .first()
    spot_data = spot.get_dict()
    if is_shorediving and sd_spot:
      spot_data['sd_url'] = sd_spot.get_url()
      spot_data['country'] = sd_spot.get_region_dict()
      spot_data['area_one'] = sd_spot.get_destination_dict()
      spot_data['area_two'] = None
      spot_data['locality'] = None
    else:
      if spot_data['locality']:
        spot_data['locality'] = spot.locality.get_dict(spot.country, spot.area_one, spot.area_two)
      if spot_data['area_two']:
        spot_data['area_two'] = spot.area_two.get_dict(spot.country, spot.area_one)
      if spot_data['area_one']:
        spot_data['area_one'] = spot.area_one.get_dict(spot.country)
      if spot_data['country']:
        spot_data['country'] = spot.country.get_dict()
    beach_id = spot.id
    if not spot.location_google and spot.latitude and spot.longitude:
      spot_data['location_google'] = ('http://maps.google.com/maps?q=%(latitude)f,%(longitude)f'
        % { 'latitude': spot.latitude, 'longitude': spot.longitude}
      )
    spot_data["ratings"] = get_summary_reviews_helper(beach_id)
    return { 'data': spot_data }
  query = Spot.query
  if request.args.get('unverified'):
    query = query.filter(Spot.is_verified.isnot(True))
  else:
    query = query.filter(Spot.is_verified.isnot(False))
    query = query.filter(Spot.is_deleted.isnot(True))
  locality_name = request.args.get('locality')
  area_two_name = request.args.get('area_two')
  area_one_name = request.args.get('area_one')
  country_name = request.args.get('country')
  if locality_name:
    area_two_spot_query = Spot.area_two.has(short_name=area_two_name)
    area_two_area_query = Locality.area_two.has(short_name=area_two_name)
    if area_two_name == '_':
      area_two_spot_query = sql.true()
      area_two_area_query = sql.true()
    query = query.filter(
      and_(
        Spot.locality.has(short_name=locality_name),
        area_two_spot_query,
        Spot.area_one.has(short_name=area_one_name),
        Spot.country.has(short_name=country_name),
      )
    )
    area = Locality.query \
      .options(joinedload('area_two')) \
      .options(joinedload('area_one')) \
      .options(joinedload('country')) \
      .filter(
        Locality.short_name==locality_name,
        area_two_area_query,
        Locality.area_one.has(short_name=area_one_name),
        Locality.country.has(short_name=country_name),
      ) \
      .first_or_404()
  elif area_two_name:
    query = query.filter(
      and_(
        Spot.area_two.has(short_name=area_two_name),
        Spot.area_one.has(short_name=area_one_name),
        Spot.country.has(short_name=country_name),
      )
    )
    area = AreaTwo.query \
      .options(joinedload('area_one')) \
      .options(joinedload('country')) \
      .filter(
        and_(
          AreaTwo.short_name==area_two_name,
          AreaTwo.area_one.has(short_name=area_one_name),
          AreaTwo.country.has(short_name=country_name),
        )
      ) \
      .first_or_404()
  elif area_one_name:
      query = query.filter(
        and_(
          Spot.area_one.has(short_name=area_one_name),
          Spot.country.has(short_name=country_name),
        )
      )
      area = AreaOne.query \
        .options(joinedload('country')) \
        .filter(
          and_(
            AreaOne.short_name==area_one_name,
            AreaOne.country.has(short_name=country_name),
          )
        ) \
        .first_or_404()
  elif country_name:
      query = query.filter(Spot.country.has(short_name=country_name))
      area = Country.query \
        .filter_by(short_name=country_name) \
        .first_or_404()
  sort_param = request.args.get('sort')
  if sort_param == 'latest':
    query = query.order_by(Spot.last_review_date.desc().nullslast())
  elif sort_param == 'most_reviewed':
    query = query.order_by(Spot.num_reviews.desc().nullslast(), Spot.rating.desc())
  elif sort_param == 'top':
    query = query.order_by(Spot.rating.desc().nullslast(), Spot.num_reviews.desc())
  else:
    query = query.order_by(Spot.num_reviews.desc().nullslast())
  if request.args.get('limit') != 'none':
    limit = request.args.get('limit') if request.args.get('limit') else 15
    query = query.limit(limit)
  query = query.options(joinedload(Spot.shorediving_data))
  spots = query.all()
  if sort_param == 'top':
    spots.sort(reverse=True, key=lambda spot: spot.get_confidence_score())
  output = []
  for spot in spots:
    spot_data = spot.get_dict()
    if request.args.get('ssg'):
      spot_data['beach_name_for_url'] = spot.get_beach_name_for_url()
    if spot.shorediving_data:
      spot_data['sd_url'] = spot.shorediving_data.get_url()
    if not spot.location_google and spot.latitude and spot.longitude:
      spot_data['location_google'] = ('http://maps.google.com/maps?q=%(latitude)f,%(longitude)f'
        % { 'latitude': spot.latitude, 'longitude': spot.longitude}
      )
    output.append(spot_data)
  resp = { 'data': output }
  if area:
    area_data = area.get_dict()
    if area_data.get('area_two'):
      area_data['area_two'] = area_data.get('area_two').get_dict(area.country, area.area_one)
    if area_data.get('area_one'):
      area_data['area_one'] = area_data.get('area_one').get_dict(area.country)
    if area_data.get('country'):
      area_data['country'] = area_data.get('country').get_dict()
    resp['area'] = area_data
  return resp

@app.route("/spots/search")
def search_spots():
  """ Search Spots
  ---
  get:
      summary: Search
      description: search
      parameters:
          - name: query
            in: query
            description: search term
            type: string
            required: true
          - name: activity
            in: query
            description: activity filter. either "scuba", "freediving", or "snorkel"
            type: string
            required: false
          - name: difficulty
            in: query
            description: difficulty filter. either "beginner", "intermediate", or "advanced"
            type: string
            required: false
          - name: entry
            in: query
            description: entry filter. either "shore" or "boat"
            type: string
            required: false
          - name: max_depth
            in: query
            description: max_depth filter
            type: int
            required: false
          - name: max_depth_type
            in: query
            description: max_depth filter units. either "m" or "ft"
            type: string
            required: false
          - name: sort
            in: query
            description: sort either "rating" or "popularity"
            type: string
            required: false
      responses:
          200:
              description: Returns singular beach object or list of beach objects
              content:
                application/json:
                  schema: BeachSchema
  """
  search_term = request.args.get('query')
  if not search_term:
    search_term = request.args.get('search_term')
  difficulty = request.args.get('difficulty')
  activity = request.args.get('activity')
  entry = request.args.get('entry')
  sort = request.args.get('sort')
  difficulty_query = sql.true()
  entry_query = sql.true()
  activity_query = sql.true()
  sort_query = sql.true()
  if difficulty:
    difficulty_query = Spot.difficulty.__eq__(difficulty)
  # if entry:
    # entry_query = Spot.difficulty.is_(difficulty)
  # if activity:
    # activity_query = Spot.
  spots = Spot.query.filter(
    and_(
      or_(
        Spot.name.ilike('%' + search_term + '%'),
        Spot.location_city.ilike('%'+ search_term + '%'),
        Spot.description.ilike('%'+ search_term + '%')
      ),
      Spot.is_verified.isnot(False),
      Spot.is_deleted.isnot(True)),
      difficulty_query,
    ).all()
  output = []
  for spot in spots:
    spot_data = spot.get_dict()
    output.append(spot_data)
  return { 'data': output }

@app.route("/spots/add/script", methods=["POST"])
def add_spot_script():
  name = request.json.get('name')
  description = request.json.get('description')
  directions = request.json.get('directions')
  id = request.json.get('id')
  name_url = request.json.get('name_url')
  destination = request.json.get('destination')
  destination_url = request.json.get('destination_url')
  region = request.json.get('region')
  region_url = request.json.get('region_url')
  location_city = destination + ', ' + region
  area_two_id = request.json.get('area_two_id')
  area_one_id = request.json.get('area_one_id')
  country_id = request.json.get('country_id')

  sd_data = ShoreDivingData.query.filter_by(id=id).first()
  if sd_data:
    if sd_data.name:
      return 'Already exists', 404
    else:
      sd_data.name=name
      sd_data.name_url=name_url
      sd_data.destination=destination
      sd_data.destination_url=destination_url
      sd_data.region=region
      sd_data.region_url=region_url
      db.session.add(sd_data)
      db.session.commit()
      sd_data.id
      return { 'data': sd_data.get_dict() }

  spot = Spot(
    name=name,
    location_city=location_city,
    description=description + '\n\n' + directions,
    is_verified=True,
    country_id=country_id,
    area_one_id=area_one_id,
    area_two_id=area_two_id,
  )

  sd_data = ShoreDivingData(
    id=id,
    name=name,
    name_url=name_url,
    destination=destination,
    destination_url=destination_url,
    region=region,
    region_url=region_url,
    spot=spot,
  )

  db.session.add(sd_data)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  return { 'data': spot.get_dict() }

@app.route("/spots/add/wdscript", methods=["POST"])
def add_spot_wdscript():
  name = request.json.get('name')
  description = request.json.get('description')
  directions = request.json.get('directions')
  url = request.json.get('url')
  location_city = request.json.get('location_city')
  alternative = request.json.get('alternative')
  latitude = request.json.get('latitude')
  longitude = request.json.get('longitude')
  max_depth = request.json.get('max_depth')
  difficulty = request.json.get('difficulty') if request.json.get('difficulty') != 'null' else None
  tags = request.json.get('tags') if request.json.get('tags') else []

  sd_data = WannaDiveData.query.filter_by(url=url).first()
  if sd_data:
    return 'Already exists', 400

  full_description = description + '\n\n' + directions
  if alternative:
    full_description += '\n\n%(title)s is also known as %(alternative)s.' % { 'title':name, 'alternative':alternative }

  spot = Spot(
    name=name,
    location_city=location_city,
    description=full_description,
    is_verified=True,
    latitude=latitude,
    longitude=longitude,
    max_depth=max_depth,
    difficulty=difficulty,
  )

  sd_data = WannaDiveData(
    url=url,
    spot=spot,
  )

  for tag_text in tags:
    tag = Tag.query.filter(and_(Tag.text==tag_text, Tag.type=='Access')).first()
    if not tag:
      tag = Tag(
        text=tag_text,
        type='Access',
      )
    spot.tags.append(tag)

  db.session.add(spot)
  db.session.add(sd_data)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  return { 'data': spot.get_dict() }

@app.route("/spots/add/tags", methods=["POST"])
def add_spot_tags():
  url = request.args.get('url')
  sd_data = WannaDiveData.query.filter_by(url=url).first()
  if sd_data:
    return 'Already exists', 400

  spot = sd_data.spot

  for tag in tags:
    tag = Tag.query.filter(and_(Tag.text==tag.text, Tag.type==tag.type)).first()
    if not tag:
      tag = Tag(
        text=tag.text,
        type=tag.type,
      )
    spot.tags.append(tag)

  db.session.add(spot)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  return { 'data': spot.get_dict() }

# @app.route("/spots/tag/shore", methods=["POST"])
# def tag_shore_spots():
#   tag = Tag.query.filter(and_(Tag.text=='shore', Tag.type=='Access')).first()
#   if not tag:
#     tag = Tag(
#       text='shore',
#       type='Access',
#     )
#   spots = ShoreDivingData.query.all()
#   for sd_spot in spots:
#     sd_spot.spot.tags.append(tag)
#   db.session.commit()
#   return { 'data': len(spots) }

# @app.route("/spots/fix_tags")
# def tag_fix():
#   good_short_tag = Tag.query.filter_by(id=1).first()
#   remove_shore_tag = Tag.query.filter_by(id=2).first()
#   spots = Spot.query.filter(Spot.tags.any(id=2)).all()
#   edited_spots = []
#   for spot in spots:
#     if len(spot.tags)>=2:
#       if spot.tags[0].text == spot.tags[1].text:
#         spot.tags.remove(remove_shore_tag)
#         edited_spots.append(spot.get_dict())
#     elif len(spot.tags)==1:
#       if spot.tags[0].id==2:
#         spot.tags.append(good_short_tag)
#         spot.tags.remove(remove_shore_tag)
#         edited_spots.append(spot.get_dict())
#     db.session.commit()
#   return { 'num_spots': len(spots), 'data': edited_spots }

@app.route("/spots/add", methods=["POST"])
@jwt_required(optional=True)
def add_spot():
  """ Add Spot
  ---
  post:
      summary: Add Spot
      description: Add Spot
      parameters:
          - name: name
            in: body
            description: name
            type: string
            required: true
      responses:
          200:
              description: Returns singular beach object or list of beach objects
              content:
                application/json:
                  schema: BeachSchema
  """
  name = request.json.get('name')
  location_city = request.json.get('location_city')
  description = request.json.get('description')
  location_google = request.json.get('location_google')
  hero_img = request.json.get('hero_img')
  entry_map = request.json.get('entry_map')
  place_id = request.json.get('place_id')
  max_depth = request.json.get('max_depth')
  difficulty = request.json.get('difficulty')
  latitude = request.json.get('latitude')
  longitude = request.json.get('longitude')
  user = get_current_user()
  is_verified = True if user and user.admin else False

  if not name or not location_city:
    return { 'msg': 'Please enter a name and location' }, 404

  spot = Spot.query.filter(and_(Spot.name==name, Spot.location_city==location_city)).first()
  if spot:
    return { 'msg': 'Spot already exists' }, 409

  locality, area_2, area_1, country, latitude, longitude = None, None, None, None, None, None
  if place_id and not location_google:
    r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params = {
      'place_id': place_id,
      'fields': 'name,geometry,address_components,url',
      'key': os.environ.get('GOOGLE_API_KEY')
    })
    response = r.json()
    if response.get('status') == 'OK':
      result = response.get('result')
      if latitude and longitude:
        location_google = 'http://maps.google.com/maps?q={latitude},{longitude}' \
          .format(latitude=latitude, longitude=longitude)
      else:
        location_google = result.get('url')
        latitude = result.get('geometry').get('location').get('lat')
        longitude = result.get('geometry').get('location').get('lng')
      address_components = result.get('address_components')
      locality, area_2, area_1, country = get_localities(address_components)

  spot = Spot(
    name=name,
    location_city=location_city,
    description=description,
    location_google=location_google,
    hero_img=hero_img,
    entry_map=entry_map,
    is_verified=is_verified,
    submitter=user,
    google_place_id=place_id,
    latitude=latitude,
    longitude=longitude,
    max_depth=max_depth,
    difficulty=difficulty,
  )
  spot.locality = locality
  spot.area_one = area_1
  spot.area_two = area_2
  spot.country = country
  db.session.add(spot)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  if not user or not user.admin:
    message = Mail(
        from_email=('hello@zentacle.com', 'Zentacle'),
        to_emails='mayank@zentacle.com')

    message.template_id = 'd-df22c68e00c345108a3ac18ebf65bdaf'
    message.dynamic_template_data = {
        'beach_name': spot.name,
        'user_display_name': 'Logged out user',
        'description': description,
        'location': location_city,
        'url': 'https://www.zentacle.com'+spot.get_url(),
        'approve_url': 'https://www.zentacle.com/api/spots/approve?id='+spot.id,
    }
    if not os.environ.get('FLASK_ENV') == 'development':
      try:
          sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
          sg.send(message)
      except Exception as e:
          print(e.body)
  if user:
    message = Mail(
        from_email=('hello@zentacle.com', 'Zentacle'),
        to_emails=user.email)
    message.reply_to = 'mayank@zentacle.com'
    message.template_id = 'd-2280f0af94dd4a93aea15c5ec95e1760'
    message.dynamic_template_data = {
        'beach_name': spot.name,
        'first_name': user.first_name,
        'url': 'https://www.zentacle.com'+spot.get_url(),
    }
    if not os.environ.get('FLASK_ENV') == 'development':
      try:
          sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
          sg.send(message)
      except Exception as e:
          print(e.body)
  return { 'data': spot.get_dict() }, 200

@app.route("/spots/approve", methods=["GET"])
@jwt_required()
def approve_spot():
  if not get_current_user().admin:
    return { 'msg': "Only admins can do that" }, 401
  beach_id = request.args.get('id')
  spot = Spot.query.filter_by(id=beach_id).first_or_404()
  if spot.is_verified:
    spot_data = spot.get_dict()
    spot_data['submitter'] = {}
    return { 'data': spot_data, 'status': 'already verified' }
  spot.is_verified = True
  db.session.commit()
  spot.id
  user = spot.submitter
  if user:
    message = Mail(
        from_email=('hello@zentacle.com', 'Zentacle'),
        to_emails=user.email)
    message.reply_to = 'mayank@zentacle.com'
    message.template_id = 'd-7b9577485616413c95f6d7e2829c52c6'
    message.dynamic_template_data = {
        'beach_name': spot.name,
        'first_name': user.first_name,
        'url': 'https://www.zentacle.com'+spot.get_url()+'/review',
    }
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        print(e.body)
  spot_data = spot.get_dict()
  spot_data['submitter'] = {}
  return { 'data': spot_data }, 200

@app.route("/spots/patch", methods=["PATCH"])
@jwt_required()
def patch_spot():
  """ Patch Beach
    ---
    patch:
        summary: patch beach (admin only)
        description: patch beach (admin only). also include the params of the beach that you want to change in the body
        parameters:
          - name: id
            in: body
            description: beach id
            type: int
            required: true
        responses:
            200:
                description: Returns Beach object
                content:
                  application/json:
                    schema: BeachSchema
            400:
                content:
                  application/json:
                    schema:
                      Error:
                        properties:
                          msg:
                            type: string
                description: Not logged in.
  """
  if not get_current_user().admin:
    return { 'msg': "Only admins can do that" }, 401
  beach_id = request.json.get('id')
  spot = Spot.query.filter_by(id=beach_id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(spot, key, updates.get(key))
      if key == 'google_place_id':
        place_id = updates.get(key)
        if place_id == 'na':
          continue
        r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params = {
          'place_id': place_id,
          'fields': 'name,geometry,url,address_components',
          'key': os.environ.get('GOOGLE_API_KEY')
        })
        response = r.json()
        if response.get('status') == 'OK':
          if not updates.get('latitude') or not updates.get('longitude'):
            latitude = response.get('result').get('geometry').get('location').get('lat')
            longitude = response.get('result').get('geometry').get('location').get('lng')
            url = response.get('result').get('url')
            spot.latitude = latitude
            spot.longitude = longitude
            spot.location_google = url
          address_components = response.get('result').get('address_components')
          locality, area_2, area_1, country = get_localities(address_components)
          spot.locality = locality
          spot.area_one = area_1
          spot.area_two = area_2
          spot.country = country
          db.session.add(spot)
          db.session.commit()
        spot.id
    if updates.get('latitude') and updates.get('longitude'):
      latitude = updates.get('latitude')
      longitude = updates.get('longitude')
      spot.location_google = 'http://maps.google.com/maps?q={latitude},{longitude}' \
        .format(latitude=latitude, longitude=longitude)
  except ValueError as e:
    return e, 500
  db.session.commit()
  spot.id
  spot_data = spot.get_dict()
  return spot_data, 200

@app.route("/review/add", methods=["POST"])
@jwt_required()
def add_review():
  """ Add Review
  ---
  post:
      summary: Add Review
      description: Add Review
      parameters:
          - name: beach_id
            in: body
            description: beach_id
            type: integer
            required: true
          - name: title
            in: body
            description: text
            type: string
            required: false
          - name: rating
            in: body
            description: rating
            type: integer
            required: true
          - name: text
            in: body
            description: text
            type: string
            required: true
          - name: activity_type
            in: body
            description: text
            type: string
            required: true
      responses:
          200:
              description: Returns review object
              content:
                application/json:
                  schema: ReviewSchema
  """
  user_id = get_jwt_identity()
  user = None
  if user_id:
    user = get_current_user()
  if not user:
    email = request.json.get('email')
    user = User.query.filter_by(email=email).first_or_404()

  beach_id = request.json.get('beach_id')
  sd_id = request.json.get('sd_id')
  visibility = request.json.get('visibility') if request.json.get('visibility') != '' else None
  text = request.json.get('text')
  title = request.json.get('title')
  rating = request.json.get('rating')
  activity_type = request.json.get('activity_type')
  images = request.json.get('images') or []
  buddies = request.json.get('buddy_array') or []
  date_dived = dateutil.parser.isoparse(request.json.get('date_dived')) \
    if request.json.get('date_dived') \
    else datetime.utcnow()
  if not rating:
    return { 'msg': 'Please select a rating' }, 401
  if not activity_type:
    return { 'msg': 'Please select scuba or snorkel' }, 401

  if sd_id and not beach_id:
    sd_data = ShoreDivingData.query.filter_by(id=sd_id).first_or_404()
    beach_id = sd_data.spot_id

  spot = Spot.query.filter_by(id=beach_id).first()
  if not spot:
    return { 'msg': 'Couldn\'t find that spot' }, 404

  if len(buddies) > 0:
    #verify basic email format         
    unique_buddies = []
    for email in buddies:
      if not validate_email_format(email):
        return { 'msg': 'Please correct buddy email format' }, 401
      if not email.lower() in unique_buddies:
          unique_buddies.append(email.lower())

    if activity_type == 'snorkel':
      activity = 'snorkeled'
    else:
      activity = 'dived'
    if len(unique_buddies) == 1:
      text += (f" I {activity} with {len(unique_buddies)} other buddy.")
    else:  
      text += (f" I {activity} with {len(unique_buddies)} other buddies.")
    
    buddy_message = Mail(
      from_email=('hello@zentacle.com', 'Zentacle'),
      to_emails=unique_buddies)
    buddy_message.template_id = 'd-8869844be6034dd09f0d7cc27e27aa8c'
    buddy_message.dynamic_template_data = {
      'display_name': user.display_name ,
      'spot_name': spot.name,
      'spot_url': 'https://www.zentacle.com'+spot.get_url(),
    }
    try:
          sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
          sg.send(buddy_message)
    except Exception as e:
          print(e.body)

  review = Review(
    author_id=user.id,
    beach_id=beach_id,
    visibility=visibility,
    text=text,
    rating=rating,
    activity_type=activity_type,
    date_dived=date_dived,
    title=title,
  )

  for image in images:
    image = Image(
      url=image,
      beach_id=beach_id,
      user_id=user.id,
    )
    review.images.append(image)

  db.session.add(review)
  summary = get_summary_reviews_helper(beach_id)
  num_reviews = 0.0
  total = 0.0
  for key in summary.keys():
    num_reviews += summary[key]
    total += summary[key] * int(key)
  spot.num_reviews = num_reviews
  spot.rating = total/num_reviews
  if visibility and (not spot.last_review_date or date_dived > spot.last_review_date):
    spot.last_review_date = date_dived
    spot.last_review_viz = visibility
  db.session.commit()
  message = Mail(
      from_email=('hello@zentacle.com', 'Zentacle'),
      to_emails='mayank@zentacle.com')

  message.template_id = 'd-3188c5ee843443bf91c5eecf3b66f26d'
  message.dynamic_template_data = {
      'beach_name': spot.name,
      'first_name': user.first_name,
      'text': text,
      'url': 'https://www.zentacle.com'+spot.get_url(),
  }
  if not os.environ.get('FLASK_ENV') == 'development':
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        print(e.body)
  review.id
  return { 'review': review.get_dict(), 'spot': spot.get_dict() }, 200

@app.route("/review/get")
def get_reviews():
  """ Get Reviews
  ---
  get:
      summary: Get Review
      description: Get Review
      parameters:
          - name: beach_id
            in: body
            description: beach_id
            type: integer
            required: true
          - name: limit
            in: body
            description: limit on number of reviews to fetch
            type: integer
            required: false
          - name: offset
            in: body
            description: offset to start if paginating through reviews
            type: integer
            required: false
      responses:
          200:
              description: Returns review object
              content:
                application/json:
                  schema: ReviewSchema
  """
  sd_id = request.args.get('sd_review_id')
  if sd_id:
    review = Review.query.filter(Review.shorediving_data.has(shorediving_id=sd_id)).first()
    if review:
      data = review.get_dict()
      data['user'] = review.user.get_dict()
      return { 'data': [data] }
  beach_id = request.args.get('beach_id')
  limit = request.args.get('limit')
  offset = int(request.args.get('offset')) if request.args.get('offset') else 0

  query = Review.query.options(joinedload('user')) \
    .options(joinedload('shorediving_data')) \
    .options(joinedload('images')) \
    .order_by(Review.date_posted.desc()) \
    .filter_by(beach_id=beach_id)
  if limit:
    query = query.limit(limit)
  if offset:
    query = query.offset(offset)
  reviews = query.all()
  output = []
  for review in reviews:
    data = review.get_dict()
    data['user'] = review.user.get_dict()
    try:
      data['shorediving_data'] = review.shorediving_data.get_dict()
    except Exception:
      pass
    image_data = []
    signedUrls = []
    for image in review.images:
      image_data.append(image.get_dict())
      signedUrls.append(create_unsigned_url(image.url, 'reviews', os.environ.get('S3_BUCKET_NAME')))
    data['images'] = image_data
    data['signedUrls'] = signedUrls
    output.append(data)
  return { 'data': output, 'next_offset': offset + len(output) }

# returns count for each rating for individual beach/area ["1"] ["2"] ["3"], etc
# returns count for total ratings ["total"]
# returns average rating for beach ["average"]
@app.route("/review/getsummary")
def get_summary_reviews():
  return {"data": get_summary_reviews_helper(request.args.get('beach_id'))}

def get_summary_reviews_helper(beach_id):
  reviews = db.session.query(
    db.func.count(Review.rating),
    Review.rating
  ).filter_by(beach_id=beach_id).group_by(Review.rating).all()
  #average = db.session.query(db.func.avg(Review.rating)).filter_by(beach_id=beach_id).first()
  output = {}
  for review in reviews:
    output[str(review[1])] = review[0]
  #output["average"] = average[0][0]
  for i in range(1, 6):
    num = str(i)
    try:
      output[num]
    except:
      output[num] = 0

  return output

@app.route("/review/patch", methods=["PATCH"])
def patch_review():
  # TODO: Change this function to be auth protected
  """ Patch Review
    ---
    patch:
        summary: patch review
        description: patch review. include the id and any specific params of the review that you want to change in the body
        parameters:
          - name: id
            in: body
            description: beach id
            type: int
            required: true
          - name: datetime
            in: body
            description: date and time in UTC format
            type: string
            required: false
          - name: dive_length
            in: body
            description: amount of time in water
            type: int
            required: false
          - name: difficulty
            in: body
            description: difficulty
            type: string
            required: false
          - name: max_depth
            in: body
            description: max depth
            type: int
            required: false
          - name: water_temp
            in: body
            description: water temp
            type: number
            required: false
          - name: air_temp
            in: body
            description: air temp
            type: number
            required: false
          - name: visibility
            in: body
            description: visibility (1-5)
            type: int
            required: false
          - name: activity_type
            in: body
            description: activity_type (scuba, snorkel, freediving)
            type: string
            required: false
          - name: entry
            in: body
            description: entry (shore, boat)
            type: string
            required: false
          - name: weight
            in: body
            description: weight
            type: int
            required: false
          - name: start_air
            in: body
            description: start air
            type: int
            required: false
          - name: end_air
            in: body
            description: end air
            type: int
            required: false
          - name: air_type
            in: body
            description: air type (normal, ean32, ean36)
            type: string
            required: false
        responses:
            200:
                description: Returns Beach object
                content:
                  application/json:
                    schema: BeachSchema
            400:
                content:
                  application/json:
                    schema:
                      Error:
                        properties:
                          msg:
                            type: string
                description: Not logged in.
  """
  beach_id = request.json.get('id')
  spot = Review.query.filter_by(id=beach_id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(spot, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  spot_data = spot.get_dict()
  return spot_data, 200

@app.route("/spots/delete")
def delete_spot():
  id = request.args.get('id')

  beach = Spot.query \
    .filter_by(id=id) \
    .options(joinedload(Spot.images)) \
    .first_or_404()
  for image in beach.images:
    Image.query.filter_by(id=image.id).delete()
  for review in beach.reviews:
    Review.query.filter_by(id=review.id).delete()

  if beach.shorediving_data:
    ShoreDivingData.query.filter_by(id=beach.shorediving_data.id).delete()

  Spot.query.filter_by(id=id).delete()
  db.session.commit()
  return {}

@app.route("/review/delete", methods=["POST"])
def delete_review():
  review_id = request.args.get('review_id')
  keep_images = request.args.get('keep_images')

  review = Review.query \
    .filter_by(id=review_id) \
    .options(joinedload(Review.images)) \
    .first_or_404()
  beach_id = review.beach_id
  for image in review.images:
    if not keep_images:
      Image.query.filter_by(id=image.id).delete()
    else:
      image.review_id = None

  if review.shorediving_data:
    ShoreDivingReview.query.filter_by(id=review.shorediving_data.id).delete()

  Review.query.filter_by(id=review_id).delete()
  db.session.commit()
  spot = Spot.query.filter_by(id=beach_id).first()
  summary = get_summary_reviews_helper(beach_id)
  num_reviews = 0.0
  total = 0.0
  for key in summary.keys():
    num_reviews += summary[key]
    total += summary[key] * int(key)
  spot.num_reviews = num_reviews
  if num_reviews:
    spot.rating = total/num_reviews
  else:
    spot.rating = None
  db.session.commit()
  return {}

@app.route("/spots/recs")
@jwt_required(optional=True)
def get_recs():
  """ Recommended Sites
  ---
  get:
      summary: Recommended Sites
      description: Recommended sites for a specific user based on where they have already visited
      responses:
          200:
              description: Returns array of beaches/dive sites
              content:
                application/json:
                  schema: BeachSchema
  """
  user_id = get_jwt_identity()
  if not user_id:
    return { 'data': {} }, 401
  # (SELECT * FROM SPOT a LEFT JOIN REVIEW b ON a.id = b.beach_id WHERE b.author_id = user_id) as my_spots
  # SELECT * FROM SPOT A LEFT JOIN my_spots B ON A.id = B.id WHERE b.id IS NULL
  spots_been_to = db.session.query(Spot.id) \
    .join(Review, Spot.id == Review.beach_id, isouter=True) \
    .filter(Review.author_id==user_id).subquery()
  spots = Spot.query \
    .filter(Spot.id.not_in(spots_been_to)) \
    .filter(Spot.is_verified.isnot(False)) \
    .filter(Spot.is_deleted.isnot(True)) \
    .order_by(Spot.num_reviews.desc().nullslast(), Spot.rating.desc()) \
    .limit(25) \
    .all()
  data = []
  for spot in spots:
    data.append(spot.get_dict())

  return { 'data': data }

fake_users = [
  'Barbara Moreno',
  'Mary Lash',
  'Hiram Lee',
  'Carmen Flowers',
  'Emily Arnold',
  'Jeffrey Smith',
  'George Stephenson',
  'Nelda Paschall',
  'Linda McGinnis',
  'Eduardo Jones',
  'Roy Kawamura',
  'Susan Landers',
]

@app.route("/review/fake", methods=["POST"])
def submit_fake_review():
  beach_id = request.json.get('beach_id')
  import random
  found_one = False
  while not found_one:
    fakename = random.choice(fake_users)
    user = User.query.filter_by(display_name=fakename).first()
    if not user:
      continue
    review = Review.query.filter(and_(Review.author_id == user.id, Review.beach_id == beach_id)).first()
    if not review:
      found_one = True

  visibility = request.json.get('visibility') if request.json.get('visibility') != '' else None
  text = request.json.get('text')
  rating = request.json.get('rating')
  activity_type = request.json.get('activity_type')
  if not rating:
    return { 'msg': 'Please select a rating' }, 401
  if not activity_type:
    return { 'msg': 'Please select scuba or snorkel' }, 401

  review = Review(
    author_id=user.id,
    beach_id=beach_id,
    visibility=visibility,
    text=text,
    rating=rating,
    activity_type=activity_type,
  )
  db.session.add(review)

  spot = Spot.query.filter_by(id=beach_id).first()
  if not spot.num_reviews:
    spot.num_reviews = 1
    spot.rating = rating
  else:
    new_rating = str(round(((float(spot.rating) * (spot.num_reviews*1.0)) + rating) / (spot.num_reviews + 1), 2))
    spot.rating = new_rating
    spot.num_reviews += 1
  spot.last_review_date = datetime.utcnow()
  spot.last_review_viz = visibility
  db.session.commit()
  return 'Done', 200

@app.route("/user/register/fake", methods=["POST"])
def user_signup_fake():
  display_name = request.json.get('display_name')
  username = display_name.replace(" ", "_").lower()
  first_name = display_name.split(' ')[0]
  last_name = display_name.split(' ')[1]
  email = username + '@zentacle.com'
  unencrypted_password = 'password'
  password = bcrypt.hashpw(unencrypted_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

  user = User.query.filter_by(display_name=display_name).first()
  if user:
    return { 'msg': 'A fake account with this name already exists' }, 400

  user = User(
    first_name=first_name,
    last_name=last_name,
    display_name=display_name,
    email=email,
    password=password,
    username=username,
    is_fake=True,
  )
  db.session.add(user)
  db.session.commit()
  user.id
  return user.get_dict()

@app.route("/imagesurls")
def get_images():
    images = Image.query.all()
    output = []
    for image in images:
      dictionary = image.get_dict()
      dictionary['signedurl'] = create_presigned_url_local('reviews/' + dictionary['url'])
      output.append(dictionary)
    return { 'data': output }
           

@app.route("/beachimages")
def get_beach_images():
    beach_id = request.args.get('beach_id')
    output = []
    images = Image.query.filter_by(beach_id=beach_id).all()
    for image in images:
      dictionary = image.get_dict()
      dictionary['signedurl'] = create_unsigned_url(dictionary['url'], 'reviews', os.environ.get('S3_BUCKET_NAME'))
      output.append(dictionary)
    return {'data': output}

@app.route("/reviewimages")
def get_review_images():
    review_id = request.args.get('review_id')
    output = []
    images = Image.query.filter_by(review_id=review_id).all()
    for image in images:
      dictionary = image.get_dict()
      dictionary['signedurl'] = create_presigned_url_local('reviews/' + dictionary['url'])
      output.append(dictionary)
    return {'data': output}

def create_unsigned_url(filename, folder, bucket):
  return f'https://{bucket}.s3.amazonaws.com/{folder}/{filename}'

def create_presigned_url_local(filename, expiration=3600):
    """Generate a presigned URL to share an S3 object
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """
    bucket_name = os.environ.get('S3_BUCKET_NAME')
    object_name = filename
    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3',)
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return {'data': response}

@app.route("/upload", methods=["POST"])
@jwt_required()
def upload():
  import uuid
  # check if the post request has the file part
  if 'file' not in request.files:
      return 422, 'No file included'
  upload_file = request.files['file']
  s3_key = str(uuid.uuid4())
  user = get_current_user()
  contents = upload_file.file.read()
  result = boto3.client("s3").upload_fileobj(io.BytesIO(contents), os.environ.get('S3_BUCKET_NAME'), s3_key)
  return 

@app.route("/s3-upload")
def create_presigned_post():
    bucket_name = os.environ.get('S3_BUCKET_NAME')
    object_name = request.args.get('file')
    expiration=3600

    # Generate a presigned S3 POST URL
    s3_client = boto3.client('s3', region_name='us-east-1')
    try:
        response = s3_client.generate_presigned_post(Bucket=bucket_name,
                                                     Key=object_name,
                                                     ExpiresIn=expiration,
                                                     Fields={
                                                       'acl': 'public-read',
                                                     },
                                                     Conditions=[{
                                                       'acl': 'public-read',
                                                     }])
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL and required fields
    return response

@app.route("/user/get")
def get_user():
    """ Get User
    ---
    get:
        summary: Get User
        description: Get User (and their reviews)
        parameters:
            - name: username
              in: body
              description: username
              type: string
              required: true
        responses:
            200:
                description: Returns user object
                content:
                  application/json:
                    schema: UserSchema
    """
    username = request.args.get('username')
    if not username:
      return {
        'msg': 'Include a username in the request. If you are trying to get the logged in user, use /user/me'
      }, 422
    user = User.query \
      .options(joinedload('reviews')) \
      .filter(func.lower(User.username)==username.lower()).first()
    if not user:
      return { 'msg': 'User doesn\'t exist' }, 404
    user_data = user.get_dict()
    reviews_data = []
    for review in user.reviews:
      review.spot
      review_data = review.get_dict()
      review_data['spot'] = review.spot.get_dict()
      reviews_data.append(review_data)
    user_data['reviews'] = reviews_data
    return { 'data': user_data }

@app.route("/review/add/shorediving", methods=["POST"])
def add_shore_review():
  shorediving_beach_id = request.json.get('beach_id')
  snorkel=request.json.get('snorkel')
  beginner=request.json.get('beginner')
  intermediate=request.json.get('intermediate')
  advanced=request.json.get('advanced')
  night=request.json.get('night')
  shorediving_id=request.json.get('review_id')

  beach = ShoreDivingData.query.filter_by(id=shorediving_beach_id).first()
  if not beach:
    return 'beach doesnt exist', 403
  beach_id = beach.spot_id

  display_name = request.json.get('reviewer_name')
  username = demicrosoft(display_name)
  user = User.query.filter_by(username=username).first()
  first_name = display_name.split(' ')[0]
  email = request.json.get('reviewer_email')
  if not user:
    user = User(
      username=username,
      display_name=display_name,
      first_name=first_name,
      email=email if email else 'noreply+'+username+'@zentacle.com',
    )
    db.session.add(user)

  visibility = request.json.get('visibility') if request.json.get('visibility') != '' else None
  text = request.json.get('review_text')
  rating = max([snorkel, beginner, intermediate, advanced, night])
  activity_type = 'scuba'
  date_posted = dateutil.parser.isoparse(request.json.get('date_dived'))
  date_dived = dateutil.parser.isoparse(request.json.get('date_dived')) \
    if request.json.get('date_dived') \
    else datetime.utcnow()
  if not rating:
    return { 'msg': 'Please select a rating' }, 401
  if not activity_type:
    return { 'msg': 'Please select scuba or snorkel' }, 401

  shorediving_data = ShoreDivingReview.query.filter_by(shorediving_id=shorediving_id).first()
  if shorediving_data:
    if shorediving_data.entry:
      return 'already exists', 401
    else:
      shorediving_data.entry=request.json.get('entry')
      shorediving_data.bottom=request.json.get('bottom')
      shorediving_data.reef=request.json.get('reef')
      shorediving_data.animal=request.json.get('animal')
      shorediving_data.plant=request.json.get('plant')
      shorediving_data.facilities=request.json.get('facilities')
      shorediving_data.crowds=request.json.get('crowds')
      shorediving_data.roads=request.json.get('roads')
      shorediving_data.snorkel=request.json.get('snorkel')
      shorediving_data.beginner=request.json.get('beginner')
      shorediving_data.intermediate=request.json.get('intermediate')
      shorediving_data.advanced=request.json.get('advanced')
      shorediving_data.night=request.json.get('night')
      shorediving_data.visibility=request.json.get('visibility')
      shorediving_data.current=request.json.get('current')
      shorediving_data.surf=request.json.get('surf')
      shorediving_data.average=request.json.get('average')
      db.session.add(shorediving_data)
      db.session.commit()
      shorediving_data.id
      shorediving_data.shorediving_url
      return { 'data', shorediving_data.get_dict() }

  review = Review(
    user=user,
    beach_id=beach_id,
    visibility=visibility,
    text=text,
    rating=rating,
    activity_type=activity_type,
    date_dived=date_dived,
    date_posted=date_posted,
  )

  shorediving_data = ShoreDivingReview(
    shorediving_id=shorediving_id,
    entry=request.json.get('entry'),
    bottom=request.json.get('bottom'),
    reef=request.json.get('reef'),
    animal=request.json.get('animal'),
    plant=request.json.get('plant'),
    facilities=request.json.get('facilities'),
    crowds=request.json.get('crowds'),
    roads=request.json.get('roads'),
    snorkel=request.json.get('snorkel'),
    beginner=request.json.get('beginner'),
    intermediate=request.json.get('intermediate'),
    advanced=request.json.get('advanced'),
    night=request.json.get('night'),
    visibility=request.json.get('visibility'),
    current=request.json.get('current'),
    surf=request.json.get('surf'),
    average=request.json.get('average'),
    review=review,
  )

  db.session.add(review)
  db.session.add(shorediving_data)

  spot = Spot.query.filter_by(id=beach_id).first()
  
  if not spot:
    return { 'msg': 'Couldn\'t find that spot' }, 404
  summary = get_summary_reviews_helper(beach_id)
  num_reviews = 0.0
  total = 0.0
  for key in summary.keys():
    num_reviews += summary[key]
    total += summary[key] * int(key)
  spot.num_reviews = num_reviews
  spot.rating = total/num_reviews
  if visibility and (not spot.last_review_date or date_dived > spot.last_review_date):
    spot.last_review_date = date_dived
    spot.last_review_viz = visibility
  db.session.commit()
  review.id
  return { 'msg': 'all done' }, 200

@app.route("/spot/recalc", methods=["GET"])
def recalc_spot_rating():
  beach_id = request.args.get('beach_id')
  spot = Spot.query.filter_by(id=beach_id).first()
  summary = get_summary_reviews_helper(beach_id)
  num_reviews = 0.0
  total = 0.0
  for key in summary.keys():
    num_reviews += summary[key]
    total += summary[key] * int(key)
  spot.num_reviews = num_reviews
  if num_reviews:
    spot.rating = total/num_reviews
  else:
    spot.rating = None
  db.session.commit()
  spot.id
  return { 'data': spot.get_dict() }

@app.route("/search/location")
def search_location():
  input = request.args.get('input')
  params = {
    'key': os.environ.get('GOOGLE_API_KEY'),
    'input': input,
    'inputtype': 'textsearch',
    'fields': 'name,formatted_address,place_id',
  }
  r = requests.get('https://maps.googleapis.com/maps/api/place/textsearch/json', params=params)
  return r.json()

@app.route("/spots/nearby/v1")
def nearby_locations_v1():
  """ Nearby Locations
  ---
  post:
      summary: Nearby locations given a specific dive site
      description: Nearby locations given a specific dive site
      parameters:
          - name: beach_id
            in: body
            description: beach_id
            type: integer
            required: true
      responses:
          200:
              description: Returns list of beach objects
              content:
                application/json:
                  schema: BeachSchema
          400:
              content:
                application/json:
                  schema:
                    msg: string
              description: No lat/lng or other location data found for given location
  """
  beach_id = request.args.get('beach_id')
  spot = Spot.query \
    .options(joinedload(Spot.shorediving_data)) \
    .filter_by(id=beach_id) \
    .first_or_404()
  startlat = spot.latitude
  startlng = spot.longitude
  if not startlat or not startlng:
    spots = []
    if spot.shorediving_data:
      spots = Spot.query \
        .filter(Spot.shorediving_data.has(destination_url=spot.shorediving_data.destination_url)) \
        .limit(10) \
        .all()
    else:
      spots = Spot.query.filter(Spot.has(country_id=spot.country_id)).limit(10).all()
    output=[]
    for spot in spots:
      spot_data = spot.get_dict()
      output.append(spot_data)
    if len(output):
      return { 'data': output }
    else:
      return { 'msg': 'No lat/lng, country_id, or sd_data for this spot ' }, 400
  query = "SELECT id, name, hero_img, rating, num_reviews, location_city, difficulty, SQRT(POW(69.1 * (latitude - %(startlat)s), 2) + POW(69.1 * (%(startlng)s - longitude) * COS(latitude / 57.3), 2)) AS distance FROM spot WHERE id != %(beach_id)s AND is_verified=true ORDER BY distance LIMIT 10;" % {'startlat':startlat, 'startlng':startlng, 'beach_id':beach_id}
  # used for testing locally on sqlite since it doesn't support any of the math functions in sql
  # query = "SELECT id, name, hero_img, rating, num_reviews, location_city, difficulty, %(startlng)s + %(startlat)s AS distance FROM spot WHERE latitude is NOT NULL AND longitude is NOT NULL ORDER BY distance LIMIT 10;" % {'startlat':startlat, 'startlng':startlng}
  try:
    results = db.engine.execute(query)
    data = []
    for id, name, hero_img, rating, num_reviews, location_city, difficulty, distance in results:
      data.append({
        'id': id,
        'name': name,
        'hero_img': hero_img,
        'rating': rating,
        'num_reviews': num_reviews,
        'distance': distance,
        'location_city': location_city,
        'difficulty': difficulty,
        'url': Spot.create_url(id, name),
      })
    return { 'data': data }
  except OperationalError as e:
    if "no such function: sqrt" in str(e).lower():
      query = "SELECT id, name, hero_img, rating, num_reviews, location_city, difficulty, %(startlng)s + %(startlat)s AS distance FROM spot WHERE latitude is NOT NULL AND longitude is NOT NULL ORDER BY distance LIMIT 10;" % {'startlat':startlat, 'startlng':startlng}
      results = db.engine.execute(query)
      data = []
      for id, name, hero_img, rating, num_reviews, location_city, difficulty, distance in results:
        data.append({
          'id': id,
          'name': name,
          'hero_img': hero_img,
          'rating': rating,
          'num_reviews': num_reviews,
          'distance': distance,
          'location_city': location_city,
          'difficulty': difficulty,
          'url': Spot.create_url(id, name),
        })
      return { 'data': data }
    else:
      return { 'msg': str(e) }, 500
  except Exception as e:
    return { 'msg': str(e) }, 500

@app.route("/spots/nearby")
def nearby_locations():
  """ Nearby Locations
  ---
  post:
      summary: Nearby locations given a specific dive site
      description: Nearby locations given a specific dive site
      parameters:
          - name: beach_id
            in: body
            description: beach_id
            type: integer
            required: true
      responses:
          200:
              description: Returns list of beach objects
              content:
                application/json:
                  schema: BeachSchema
          400:
              content:
                application/json:
                  schema:
                    msg: string
              description: No lat/lng or other location data found for given location
  """
  beach_id = request.args.get('beach_id')
  spot = Spot.query \
    .options(joinedload(Spot.shorediving_data)) \
    .filter_by(id=beach_id) \
    .first_or_404()
  startlat = spot.latitude
  startlng = spot.longitude
  if not startlat or not startlng:
    spots = []
    if spot.shorediving_data:
      try:
        spots = Spot.query \
          .filter(Spot.shorediving_data.has(destination_url=spot.shorediving_data.destination_url)) \
          .limit(10) \
          .all()
      except AttributeError as e:
        return { 'msg': str(e) }
    else:
      try:
        spots = Spot.query.filter(Spot.has(country_id=spot.country_id)).limit(10).all()
      except AttributeError as e:
        return { 'msg': str(e) }
    output=[]
    for spot in spots:
      spot_data = spot.get_dict()
      output.append(spot_data)
    if len(output):
      return { 'data': output }
    else:
      return { 'msg': 'No lat/lng, country_id, or sd_data for this spot ' }, 400

  results = []
  try:
    query = Spot.query.filter(and_(
      Spot.is_verified == True,
      Spot.is_deleted.is_not(True),
      Spot.id != spot.id,
    )).options(joinedload('locality')).order_by(Spot.distance(startlat, startlng)).limit(10)
    results = query.all()
  except OperationalError as e:
    if "no such function: sqrt" in str(e).lower():
      query = Spot.query.filter(and_(
        Spot.is_verified == True,
        Spot.is_deleted.is_not(True),
        Spot.id != spot.id,
      )).options(joinedload('locality')).order_by(Spot.sqlite3_distance(startlat, startlng)).limit(10)
      results = query.all()
    else:
      return { 'msg': str(e) }, 500
  except Exception as e:
    return { 'msg': str(e) }, 500
  data = []
  for result in results:
    temp_data = result.get_dict()
    if result.locality and result.locality.url:
      temp_data['locality'] = {
        'url': result.locality.url
      }
    else:
      temp_data.pop('locality', None)
    data.append(temp_data)
  return { 'data': data }

@app.route("/spots/location")
def get_location_spots():
  type = request.args.get('type')
  name = request.args.get('name')
  locality = None
  if type == 'locality':
    locality = Locality.query.filter_by(name=name).first_or_404()
  if type == 'area_one':
    locality = AreaOne.query.filter_by(name=name).first_or_404()
  if type == 'area_two':
    locality = AreaTwo.query.filter_by(name=name).first_or_404()
  if type == 'country':
    locality = Country.query.filter_by(name=name).first_or_404()
  data = []
  for spot in locality.spots:
    data.append(spot.get_dict())
  return { 'data': data }

@app.route("/locality/locality")
def locality_get():
  limit = request.args.get('limit') if request.args.get('limit') else 15
  country_short_name = request.args.get('country')
  area_one_short_name = request.args.get('area_one')
  area_two_short_name = request.args.get('area_two')
  localities = Locality.query
  if country_short_name:
    localities = localities.filter(Locality.country.has(short_name=country_short_name))
  if area_one_short_name:
    localities = localities.filter(Locality.area_one.has(short_name=area_one_short_name))
  if area_two_short_name:
    localities = localities.filter(Locality.area_two.has(short_name=area_two_short_name))
  localities = localities \
    .options(joinedload('area_two')) \
    .options(joinedload('area_one')) \
    .options(joinedload('country'))
  if limit != 'none':
    localities = localities.limit(limit)
  localities = localities.all()
  data = []
  for locality in localities:
    locality_data = locality.get_dict()
    if locality_data.get('area_two'):
      locality_data['area_two'] = locality_data.get('area_two').get_simple_dict()
    if locality_data.get('area_one'):
      locality_data['area_one'] = locality_data.get('area_one').get_simple_dict()
    if locality_data.get('country'):
      locality_data['country'] = locality_data.get('country').get_simple_dict()
    data.append(locality_data)
  #   if 'url' in locality_data and not locality.url:
  #     locality.url = locality_data['url']
  # db.session.commit()
  return { 'data': data }

@app.route("/locality/area_two")
def get_area_two():
  limit = request.args.get('limit') if request.args.get('limit') else 25
  country_short_name = request.args.get('country')
  area_one_short_name = request.args.get('area_one')
  localities = AreaTwo.query
  if country_short_name:
    localities = localities.filter(AreaTwo.country.has(short_name=country_short_name))
  if area_one_short_name:
    localities = localities.filter(AreaTwo.area_one.has(short_name=area_one_short_name))
  localities = localities \
    .options(joinedload('area_one')) \
    .options(joinedload('country'))
  if limit != 'none':
    localities = localities.limit(limit)
  localities = localities.all()
  data = []
  for locality in localities:
    locality_data = locality.get_dict()
    if locality.area_one:
      locality_data['area_one'] = locality.area_one.get_simple_dict()
    if locality.country:
      locality_data['country'] = locality.country.get_simple_dict()
    data.append(locality_data)
  return { 'data': data }

@app.route("/locality/area_one")
def get_area_one():
  country_short_name = request.args.get('country')
  country = Country.query.filter_by(short_name=country_short_name).first()
  localities = AreaOne.query
  if country:
    localities = localities.filter_by(country_id=country.id)
  localities = localities.options(joinedload('country')) \
    .all()
  data = []
  for locality in localities:
    locality_data = locality.get_dict()
    if locality_data.get('country'):
      locality_data['country'] = locality_data.get('country').get_simple_dict()
    data.append(locality_data)
  return { 'data': data }

@app.route("/locality/country")
def get_country():
  sq = db.session.query(Spot.country_id, func.count(Spot.id).label('count')).group_by(Spot.country_id).subquery()
  localities = db.session.query(Country, sq.c.count).join(sq, sq.c.country_id == Country.id).all()
  data = []
  for (locality, count) in localities:
    dict = locality.get_dict()
    dict['num_spots'] = count
    data.append(dict)
  data.sort(reverse=True, key=lambda country:country['num_spots'])
  return { 'data': data }

@app.route("/loc/country/patch", methods=["PATCH"])
def patch_country():
  id = request.json.get('id')
  loc = Country.query.filter_by(id=id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(loc, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  loc.id
  return loc.get_dict(), 200

@app.route("/loc/area_one/patch", methods=["PATCH"])
def patch_loc_one():
  id = request.json.get('id')
  loc = AreaOne.query.filter_by(id=id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(loc, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  loc.id
  return loc.get_dict(), 200

@app.route("/loc/area_two/patch", methods=["PATCH"])
def patch_loc_two():
  id = request.json.get('id')
  loc = AreaTwo.query.filter_by(id=id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(loc, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  loc.id
  return loc.get_dict(), 200

@app.route("/locality/<country>/<area_one>")
def get_wildcard_locality(country, area_one):
  locality = AreaOne.query \
    .filter(
      and_(
        AreaOne.short_name==area_one,
        AreaOne.country.has(short_name=country)
      )
    ).first_or_404()
  data = []
  for spot in locality.spots:
    data.append(spot.get_dict())
  return { 'data': data }

@app.route("/spots/add_place_id", methods=["POST"])
def add_place_id():
  spots = Spot.query.filter(Spot.is_verified.isnot(False)).all()
  skipped = []
  for spot in spots:
    if spot.google_place_id and spot.google_place_id != "na":
      place_id = spot.google_place_id
      r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params = {
          'place_id': place_id,
          'fields': 'address_components',
          'key': os.environ.get('GOOGLE_API_KEY')
        })
      response = r.json()
      if response.get('status') == 'OK':
        address_components = response.get('result').get('address_components')
        locality, area_2, area_1, country = get_localities(address_components)
        spot.locality = locality
        spot.area_one = area_1
        spot.area_two = area_2
        spot.country = country
        db.session.add(spot)
        db.session.commit()
        spot.id
      else:
        skipped.append({'name': spot.name})
    else:
      skipped.append({'name': spot.name})
  return { 'data': skipped }

@app.route("/search/autocomplete")
def search_autocomplete():
  search_term = request.args.get('q')
  spots = Spot.query.filter(
    Spot.name.ilike('%' + search_term + '%')
  ).limit(5).all()
  output = []
  for spot in spots:
    spot_data = {
      'label': spot.name,
      'type': 'spot',
      'url': spot.get_url(),
    }
    output.append(spot_data)
  return { 'data': output }

@app.route("/spots/patch/shorediving", methods=["POST"])
def add_shorediving_pic():
  id = request.json.get('id')
  pic_url = request.json.get('url')

  shorediving = ShoreDivingData.query.filter_by(id=id).first_or_404()
  if not shorediving.spot.hero_img:
    shorediving.spot.hero_img = 'https://'+os.environ.get('S3_BUCKET_NAME')+'.s3.amazonaws.com/' + pic_url
  else:
    return 'Already has one', 401
  db.session.commit()
  shorediving.spot.id
  return { 'data': shorediving.spot.get_dict() }

@app.route("/reviews/delete", methods=["POST"])
def delete_shore_diving_ids():
  id = request.json.get('id')
  sd_review = ShoreDivingReview.query.filter_by(shorediving_id=id).first_or_404()
  review = sd_review.review
  db.session.delete(sd_review)
  db.session.delete(review)
  db.session.commit()
  return 'ok'

@app.route("/spots/add/shoredivingdata", methods=["POST"])
def add_shorediving_to_existing():
  beach_id = request.json.get('beach_id')
  sd_id = request.json.get('sd_id')
  spot = Spot.query.filter_by(id=beach_id).first_or_404()
  sd_data = ShoreDivingData(
    id=sd_id,
    spot=spot,
  )
  db.session.add(sd_data)
  db.session.commit()
  sd_data.id
  return { 'data': sd_data.get_dict() }

@app.route("/spots/add/backfill", methods=["POST"])
def backfill_shorediving_to_existing():
  name = request.json.get('name')
  id = request.json.get('id')
  name_url = request.json.get('name_url')
  destination = request.json.get('destination')
  destination_url = request.json.get('destination_url')
  region = request.json.get('region')
  region_url = request.json.get('region_url')
  area_two_id = request.json.get('area_two_id')

  spot = Spot.query.filter_by(name=name).first_or_404()
  if spot.area_two_id != area_two_id:
    return 'Couldnt find a spot in the correct region with this name', 401

  sd_spot = ShoreDivingData.query.filter_by(id=id).first()
  if sd_spot:
    return 'Already exists', 402

  sd_data = ShoreDivingData(
    id=id,
    name=name,
    name_url=name_url,
    destination=destination,
    destination_url=destination_url,
    region=region,
    region_url=region_url,
    spot=spot,
  )
  db.session.add(sd_data)
  db.session.commit()
  sd_data.id
  return { 'data': sd_data.get_dict() }

@app.route('/generate-short-names', methods=['GET'])
def backfill_short_names():
  localities = Locality.query.all()
  already_had = []
  for locality in localities:
    if not locality.short_name:
      locality.short_name = demicrosoft(locality.name).lower()
    else:
      already_had.append(locality.get_dict())
  db.session.commit()
  return { 'msg': already_had }

@app.route('/set-country')
def set_country():
  country_id = request.args.get('country_id')
  country_short_name = request.args.get('country_short_name')
  area_one_id = request.args.get('area_one_id')
  area_one_short_name = request.args.get('area_one_short_name')
  area_two_id = request.args.get('area_two_id')
  area_two_short_name = request.args.get('area_two_short_name')
  locality_id = request.args.get('locality_id')
  region_url = request.args.get('region_url')
  destination_url = request.args.get('destination_url')
  if region_url:
    spots = Spot.query.filter(Spot.shorediving_data.has(region_url=region_url)).all()
  elif destination_url:
    spots = Spot.query.filter(Spot.shorediving_data.has(destination_url=destination_url)).all()
  else:
    return 'No destination or region', 401
  if country_short_name:
    country = Country.query.filter_by(short_name=country_short_name).first()
    country_id = country.id
  if area_one_short_name:
    area_one = AreaOne.query.filter_by(short_name=area_one_short_name).first()
    area_one_id = area_one.id
  if area_two_short_name:
    area_two = AreaTwo.query.filter_by(short_name=area_two_short_name).first()
    area_two_id = area_two.id
  data = []
  for spot in spots:
    if not spot.country_id and country_id:
      spot.country_id = int(country_id)
    if not spot.area_one_id and area_one_id:
      spot.area_one_id = int(area_one_id)
    if not spot.area_two_id and area_two_id:
      spot.area_two_id = int(area_two_id)
    if not spot.locality_id and locality_id:
      spot.locality_id = int(locality_id)
    data.append(spot.get_dict())
  db.session.commit()
  return { 'data': data }

@app.route('/update-usernames')
def update_usernames():
  users = User.query.filter(
    and_(
      User.registered_on > '2021-09-11 09:45:43.152087',
      User.registered_on < '2021-09-11 20:26:26.295655'
    )
  )

  output = []
  failed = []
  for user in users:
    if '-' in user.username:
      old_username = user.username
      new_username = user.username.replace('-', '_')
      user.username = new_username
      output.append({
        "id": user.id,
        "old_username": old_username,
        "new_username": new_username,
      })
      try:
        db.session.commit()
      except Exception as e:
        failed.append(user.get_dict())
  return {
    'data': output,
    'failed': failed,
  }

@app.route("/spot/setStationId", methods=["POST"])
def add_station_id():
  spot_id = request.json.get('spotId')
  station_id = request.json.get('stationId')
  spot = Spot.query.filter_by(id=spot_id).first_or_404()
  spot.noaa_station_id = station_id
  db.session.commit()
  spot.id
  return { 'data': spot.get_dict() }

@app.route("/search/typeahead")
def get_typeahead():
  """ Search Typeahead
  ---
  get:
      summary: Typeahead locations for search bar
      description: Typeahead locations for search bar
      parameters:
          - name: query
            in: query
            description: query
            type: string
            required: true
          - name: beach_only
            in: query
            description: should only return beach spots. ie ?beach_only=True
            type: string
            required: false
      responses:
          200:
              description: Returns list of typeahead objects
              content:
                application/json:
                  schema: TypeAheadSchema
  """
  query = request.args.get('query')
  beach_only = request.args.get('beach_only')
  results = []
  spots = Spot.query.filter(Spot.name.ilike('%'+query+'%')).limit(25).all()
  for loc in spots:
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': loc.get_url(),
      'type': 'site',
      'subtext': loc.name,
    }
    results.append(result)
  if beach_only:
    return { 'data': results }

  countries = Country.query.filter(Country.name.ilike('%'+query+'%')).limit(10).all()
  area_ones = AreaOne.query.filter(AreaOne.name.ilike('%'+query+'%')).limit(10).all()
  area_twos = AreaTwo.query.filter(AreaTwo.name.ilike('%'+query+'%')).limit(10).all()
  localities = Locality.query.filter(Locality.name.ilike('%'+query+'%')).limit(10).all()
  for loc in countries:
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': loc.get_url(),
      'type': 'location',
      'subtext': loc.name,
    }
    results.append(result)
  for loc in area_ones:
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': loc.get_url(loc.country),
      'type': 'location',
      'subtext': loc.country.name,
    }
    results.append(result)
  for loc in area_twos:
    if loc.country and loc.area_one:
      result = {
        'id': loc.id,
        'text': loc.name,
        'url': loc.get_url(loc.country, loc.area_one),
        'type': 'location',
        'subtext': loc.country.name,
      }
      results.append(result)
  for loc in localities:
    if loc.country and loc.area_one and loc.area_two:
      result = {
        'id': loc.id,
        'text': loc.name,
        'url': loc.get_url(loc.country, loc.area_one, loc.area_two),
        'type': 'location',
        'subtext': loc.country.name,
      }
      results.append(result)
  return { 'data': results }

@app.route("/spots/merge", methods=["POST"])
def merge_spot():
  orig_id = request.json.get('orig_id')
  dupe_id = request.json.get('dupe_id')
  orig = Spot.query.filter_by(id=orig_id).first_or_404()
  dupe = Spot.query.filter_by(id=dupe_id).first_or_404()
  wd_data = WannaDiveData.query.filter_by(spot_id=dupe_id).first()
  if wd_data:
    wd_data.spot_id = orig.id
  if not orig.latitude or not orig.longitude:
    orig.latitude = dupe.latitude
    orig.longitude = dupe.longitude
  if not orig.difficulty:
    orig.difficulty = dupe.difficulty
  if not orig.max_depth:
    orig.max_depth = dupe.max_depth
  if not orig.rating:
    orig.rating = dupe.rating
  if not orig.last_review_viz:
    orig.last_review_viz = dupe.last_review_viz
  for tag in dupe.tags:
    if tag not in orig.tags:
      orig.tags.append(tag)
  dupe.is_deleted = True
  db.session.commit()
  orig.id
  return { 'data': orig.get_dict() }

@app.route("/spot/geocode")
def geocode():
    return 'hello world', 200
    beach_id = request.args.get('id')
    spot = Spot.query.filter_by(id=beach_id).first_or_404()
    if not spot.latitude or not spot.longitude:
      return { 'msg': 'no lat/lng' }, 422
    if spot.country:
      return { 'msg': 'already has address components' }, 422
    r = requests.get('https://maps.googleapis.com/maps/api/geocode/json', params = {
      'latlng': f'{spot.latitude},{spot.longitude}',
      'key': os.environ.get('GOOGLE_API_KEY')
    })
    response = r.json()
    if response.get('status') == 'OK':
          address_components = response.get('results')[0].get('address_components')
          locality, area_2, area_1, country = get_localities(address_components)
          if not spot.locality:
            spot.locality = locality
          if not spot.area_one:
            spot.area_one = area_1
          if not spot.area_two:
            spot.area_two = area_2
          if not spot.country:
            spot.country = country
          db.session.add(spot)
          db.session.commit()
          spot.id
    return spot.get_dict()

with app.test_request_context():
    spec.path(view=user_signup)
    spec.path(view=user_google_signup)
    spec.path(view=user_finish_signup)
    spec.path(view=patch_user)
    spec.path(view=user_login)
    spec.path(view=get_spots)
    spec.path(view=add_review)
    spec.path(view=get_reviews)
    spec.path(view=get_user)
    spec.path(view=get_recs)
    spec.path(view=nearby_locations)
    spec.path(view=get_typeahead)
    spec.path(view=patch_review)
    spec.path(view=patch_spot)
    spec.path(view=search_spots)
    # ...

@app.route("/spec")
def get_apispec():
    return jsonify(spec.to_dict())
