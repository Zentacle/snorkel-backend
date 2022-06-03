from __future__ import print_function
from flask import Flask, request, jsonify
from flask.helpers import make_response
from flask_cors import CORS
from flask_caching import Cache
import os
import os.path
import logging
import secrets
from app.models import *
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, not_, func
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
import requests
from app.scripts.openapi import spec

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
SQLALCHEMY_DATABASE_URI = (os.environ.get('DATABASE_URL').replace("://", "ql://", 1)
  if not os.environ.get('FLASK_ENV') == 'development'
  else os.environ.get('DATABASE_URL'))
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get('JWT_SECRET')
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
app.config["JWT_SESSION_COOKIE"] = False
app.config["CACHE_TYPE"] = "SimpleCache"
app.config["CACHE_DEFAULT_TIMEOUT"] = 300
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
cache = Cache(app)
jwtManager = JWTManager(app)
db.init_app(app)
migrate = Migrate(compare_type=True)
migrate.init_app(app, db)

# Register a callback function that loades a user from your database whenever
# a protected route is accessed. This should return any python object on a
# successful lookup, or None if the lookup failed for any reason (for example
# if the user has been deleted from the database).
@jwtManager.user_lookup_loader
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
@jwt_required()
def delete():
  user = get_current_user()
  if not user.admin:
    return {'msg': 'You must be an admin to that'}, 403
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
@cache.cached(query_string=True)
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
@cache.cached(query_string=True)
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
  return f'https://www.zentacle.com/image/{folder}/{filename}'

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

@app.route("/locality/locality")
@cache.cached(query_string=True)
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
@cache.cached(query_string=True)
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
@cache.cached(query_string=True)
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
@cache.cached()
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

@app.route("/search/typeahead")
@cache.cached(query_string=True)
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
  spots = Spot.query \
    .filter(Spot.name.ilike('%'+query+'%')) \
    .filter(Spot.is_deleted.is_not(True)) \
    .limit(25) \
    .all()
  for loc in spots:
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': loc.get_url(),
      'type': 'site',
      'subtext': loc.location_city,
      'data': {
        'latitude': loc.latitude,
        'longitude': loc.longitude,
        'location_city': loc.location_city,
      }
    }
    results.append(result)
  if beach_only:
    return { 'data': results }

  countries = Country.query.filter(Country.name.ilike('%'+query+'%')).limit(10).all()
  area_ones = AreaOne.query.filter(AreaOne.name.ilike('%'+query+'%')).limit(10).all()
  area_twos = AreaTwo.query.filter(AreaTwo.name.ilike('%'+query+'%')).limit(10).all()
  localities = Locality.query.filter(Locality.name.ilike('%'+query+'%')).limit(10).all()
  for loc in countries:
    url = loc.get_url()
    segments = url.split("/")
    country = segments[2]
    area_one = None
    area_two = None
    locality = None
    if len(segments) > 3:
      area_one = segments[3]
    if len(segments) > 4:
      area_two = segments[4]
    if len(segments) > 5:
      locality = segments[5]
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': url,
      'type': 'location',
      'subtext': loc.name,
      'data': {
        'country': country,
        'area_one': area_one,
        'area_two': area_two,
        'locality': locality
      }
    }
    results.append(result)
  for loc in area_ones:
    url = loc.get_url(loc.country)
    segments = url.split("/")
    country = segments[2]
    area_one = None
    area_two = None
    locality = None
    if len(segments) > 3:
      area_one = segments[3]
    if len(segments) > 4:
      area_two = segments[4]
    if len(segments) > 5:
      locality = segments[5]
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': url,
      'type': 'location',
      'subtext': loc.country.name,
      'data': {
        'country': country,
        'area_one': area_one,
        'area_two': area_two,
        'locality': locality
      }
    }
    results.append(result)
  for loc in area_twos:
    if loc.country and loc.area_one:
      url = loc.get_url(loc.country, loc.area_one)
      segments = url.split("/")
      country = segments[2]
      area_one = None
      area_two = None
      locality = None
      if len(segments) > 3:
        area_one = segments[3]
      if len(segments) > 4:
        area_two = segments[4]
      if len(segments) > 5:
        locality = segments[5]
      result = {
        'id': loc.id,
        'text': loc.name,
        'url': url,
        'type': 'location',
        'subtext': loc.country.name,
        'data': {
          'country': country,
          'area_one': area_one,
          'area_two': area_two,
          'locality': locality
        }
      }
      results.append(result)
  for loc in localities:
    if loc.country and loc.area_one and loc.area_two:
      url = loc.get_url(loc.country, loc.area_one, loc.area_two)
      segments = url.split("/")
      country = segments[2]
      area_one = None
      area_two = None
      locality = None
      if len(segments) > 3:
        area_one = segments[3]
      if len(segments) > 4:
        area_two = segments[4]
      if len(segments) > 5:
        locality = segments[5]
      result = {
        'id': loc.id,
        'text': loc.name,
        'url': url,
        'type': 'location',
        'subtext': loc.country.name,
        'data': {
          'country': country,
          'area_one': area_one,
          'area_two': area_two,
          'locality': locality
        }
      }
      results.append(result)
  return { 'data': results }

@app.route('/password/request', methods=['POST'])
def request_reset_password():
  email = request.json.get('email')
  user = User.query.filter(func.lower(User.email)==email.lower()).first_or_404()

  reset_obj = PasswordReset(
    user_id=user.id,
    token=secrets.token_urlsafe(),
  )
  db.session.add(reset_obj)
  db.session.commit()

  message = Mail(
      from_email=('hello@zentacle.com', 'Zentacle'),
      to_emails=email)

  message.template_id = 'd-61fcfe0f648c4237849621389db5c75c'
  message.reply_to = 'mayank@zentacle.com'
  message.dynamic_template_data = {
      'url': 'https://www.zentacle.com/resetpassword?token='+reset_obj.token,
  }
  try:
      sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
      sg.send(message)
  except Exception as e:
      print(e.body)

  return {'msg': 'Password reset sent, check your email for a reset link'}

@app.route('/password/reset', methods=['POST'])
def reset_password():
  token = request.json.get('token')
  password = request.json.get('password')

  reset_obj = PasswordReset.query.filter_by(token=token).first()
  if reset_obj:
    if reset_obj.token_expiry < datetime.utcnow():
      return {'msg': 'Link expired. Try reseting your password again'}, 401
    user_id = reset_obj.user_id
    user = User.query.filter_by(id=user_id).first()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user.password = hashed_password
    db.session.commit()
    refresh_token = create_refresh_token(identity=user.id)
    auth_token = create_access_token(identity=user.id)
    responseObject = {
      'status': 'success',
      'msg': 'Successfully reset password. You are now logged in',
      'auth_token': auth_token,
      'refresh_token': refresh_token
    }
    resp = make_response(responseObject)
    set_access_cookies(resp, auth_token)
    set_refresh_cookies(resp, refresh_token)
    db.session.delete(reset_obj)
    db.session.commit()
    return resp
  return {'msg': 'No token or password provided'}, 422

from app.routes import shop
app.register_blueprint(shop.bp)

from app.routes import user
app.register_blueprint(user.bp)

from app.routes import users
app.register_blueprint(users.bp)

from app.routes import review
app.register_blueprint(review.bp)

from app.routes import reviews
app.register_blueprint(reviews.bp)

from app.routes import buddy
app.register_blueprint(buddy.bp)

from app.routes import spots
app.register_blueprint(spots.bp)

from app.routes import spot
app.register_blueprint(spot.bp)

with app.test_request_context():
  pass
    # spec.path(view=user_signup)
    # spec.path(view=user_apple_signup)
    # spec.path(view=user_google_signup)
    # spec.path(view=user_finish_signup)
    # spec.path(view=patch_user)
    # spec.path(view=user_login)
    # spec.path(view=get_spots)
    # spec.path(view=add_review)
    # spec.path(view=get_reviews)
    # spec.path(view=get_user)
    # spec.path(view=get_recs)
    # spec.path(view=nearby_locations)
    # spec.path(view=get_typeahead)
    # spec.path(view=patch_review)
    # spec.path(view=patch_spot)
    # spec.path(view=search_spots)
    # spec.path(view=get_review)
    # spec.path(view=upload_file)
    # spec.path(view=get_recent_reviews)
    # ...

@app.route("/spec")
def get_apispec():
    return jsonify(spec.to_dict())
