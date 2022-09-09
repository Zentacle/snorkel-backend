from __future__ import print_function
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from flask_caching import Cache
import os
import os.path
import logging
import requests
from app.models import *
from sqlalchemy import and_, not_
from flask_jwt_extended import *
from datetime import timezone, timedelta
from flask_migrate import Migrate
import logging
import boto3
from botocore.exceptions import ClientError
from app.scripts.openapi import spec
from amplitude import Amplitude, BaseEvent

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
  client = Amplitude(os.environ.get('AMPLITUDE_API_KEY'))
  client.configuration.min_id_length = 1
  event = BaseEvent(event_type="health_check", user_id="1")
  client.track(event)
  return "Ok"

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

@app.route("/beachimages")
@cache.cached(query_string=True)
def get_beach_images():
    beach_id = request.args.get('beach_id')
    output = []
    images = Image.query.filter_by(beach_id=beach_id).all()
    for image in images:
      dictionary = image.get_dict()
      dictionary['signedurl'] = dictionary['url']
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
      dictionary['signedurl'] = dictionary['url']
      output.append(dictionary)
    return {'data': output}

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

@app.route("/spec")
def get_apispec():
    return jsonify(spec.to_dict())

@app.route("/subscription-webhook", methods=['POST'])
def subscription_webhook():
  event = request.json.get('event')
  event_type = event.get('type')
  user_id = int(event.get('app_user_id'))
  user = User.query.filter_by(id=user_id).first_or_404()

  if (
    event_type == 'INITIAL_PURCHASE'
    or event_type == 'RENEWAL'
    or event_type == 'UNCANCELLATION'
    ):
    setattr(user, 'has_pro', True)
  elif (
    event_type == 'CANCELLATION'
    or event_type == 'EXPIRATION'
    or event_type == 'SUBSCRIPTION_PAUSED'
  ):
    setattr(user, 'has_pro', False)
  db.session.commit()

  return 'OK'

@app.route("/payment-link")
def payment():
  try:
      email = request.args.get('email')
      user = User.query.filter_by(email=email).first()
      user_id = user.id if user else None
      payment_link = os.environ.get('STRIPE_PAYMENT_LINK')
      return redirect(
        f'{payment_link}?prefilled_email={email}&client_reference_id={user_id}',
        code=302
      )
  except Exception as e:
      raise Exception("Unable to create payment intent")

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
  import stripe
  event = None
  payload = request.data
  sig_header = request.headers['STRIPE_SIGNATURE']

  try:
      event = stripe.Webhook.construct_event(
          payload, sig_header, os.environ.get('STRIPE_ENDPOINT_SECRET')
      )
  except ValueError as e:
      # Invalid payload
      raise e
  except stripe.error.SignatureVerificationError as e:
      # Invalid signature
      raise e
  if event.type == 'checkout.session.completed':
      object = event.data.object
      client_reference_id = object.get('client_reference_id')
      if client_reference_id:
        subscription = object.get('subscription')
        revenuecat_api_key = os.environ.get('REVENUECAT_API_KEY')
        response = requests.post(
          'https://api.revenuecat.com/v1/receipts',
          headers={
            'X-Platform': 'stripe',
            'Authorization': f'Bearer {revenuecat_api_key}',
          },
          json={
            "app_user_id": client_reference_id,
            "fetch_token": subscription,
          }
        )
        return response
  return jsonify(success=True)

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

from app.routes import search
app.register_blueprint(search.bp)

from app.routes import loc
app.register_blueprint(loc.bp)

from app.routes import locality
app.register_blueprint(locality.bp)

from app.routes import password
app.register_blueprint(password.bp)

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
