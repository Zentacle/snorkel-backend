from __future__ import print_function
from flask import Flask, request, redirect, url_for, session, jsonify, render_template
from flask.helpers import make_response
from flask_cors import CORS
import os
import os.path
from app.models import *
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_
import bcrypt
from flask_jwt_extended import *
from datetime import timezone, timedelta

app = Flask(__name__)
app.secret_key = 'the random string'
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
#app.config["JWT_COOKIE_SECURE"] = True # Uncomment when running in production


cors = CORS(app)
jwt = JWTManager(app)
db.init_app(app)

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
  return "<h1>Welcome to DiveBriefing</h1>"

@app.route("/delete")
def delete():
  email = request.args.get('email')
  user = User.query.filter_by(email=email).first()
  db.session.delete(user)
  db.session.commit()
  return "Successfully deleted user: " + email

@app.route("/getall")
def getAllData():
    users = User.query.all()
    output = []
    for user in users:
      user_data = user.__dict__
      user_data.pop('password', None)
      user_data.pop('_sa_instance_state', None)
      output.append(user_data)
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
  display_name = request.json.get('display_name')
  email = request.json.get('email')
  username = request.json.get('username')
  profile_pic = request.json.get('profile_pic')
  unencrypted_password = request.json.get('password')
  password = bcrypt.hashpw(unencrypted_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

  user = User.query.filter_by(email=email).first()
  if user:
    return 'An account with this email already exists', 400
  user = User.query.filter_by(username=username).first()
  if user:
    return 'An account with this username already exists', 400

  user = User(
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
  return resp

"""
Save the response token as an Authorization header with the format
Authorization: Bearer <token>
"""
@app.route("/user/login", methods=["POST"])
def user_login():
  email = request.json.get('email')
  password = request.json.get('password')
  
  user = User.query.filter(or_(User.email==email, User.username==email)).first()
  if not user:
    return 'Wrong password or user does not exist', 400
  if bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
    auth_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    if auth_token:
      user_data = user.__dict__
      user_data.pop('password', None)
      user_data.pop('_sa_instance_state', None)
      responseObject = {
        'data': {
          'status': 'success',
          'message': 'Successfully logged in.',
          'auth_token': auth_token
        },
        'user': user_data
      }
      resp = make_response(responseObject)
      set_access_cookies(resp, auth_token)
      set_refresh_cookies(resp, refresh_token)
      return resp
  else:
    return 'Wrong password or user does not exist', 400

@app.route("/user/me")
@jwt_required()
def get_me():
    user = get_current_user()
    user_data = user.__dict__
    user_data.pop('password', None)
    user_data.pop('_sa_instance_state', None)
    return user_data

@app.route("/refresh")
@jwt_required(refresh=True)
def refresh_token():
  user_id = get_jwt_identity()
  auth_token = create_access_token(identity=user_id)
  return jsonify(auth_token=auth_token)

@app.route("/spots/get")
def get_spots():
  if request.args.get('beach_id'):
    beach_id = request.args.get('beach_id')
    spot = Spot.query.filter_by(id=beach_id).first()
    spot_data = spot.__dict__
    spot_data.pop('_sa_instance_state', None)
    return { 'data': spot_data }
  sort = Spot.num_reviews.desc().nullslast()
  sort_param = request.args.get('sort')
  if sort_param:
    if sort_param == 'latest':
      sort = Spot.last_review_date.desc().nullslast()
    if sort_param == 'most_reviewed':
      sort = Spot.num_reviews.desc().nullslast()
    if sort_param == 'top':
      sort = Spot.rating.desc().nullslast()
  spots = Spot.query.order_by(sort).all()
  output = []
  for spot in spots:
    spot_data = spot.__dict__
    spot_data.pop('_sa_instance_state', None)
    output.append(spot_data)
  return { 'data': output }

@app.route("/spots/search")
def search_spots():
  search_term = request.args.get('search_term')
  spots = Spot.query.filter(Spot.name.like('%' + search_term + '%')).all()
  output = []
  for spot in spots:
    spot_data = spot.__dict__
    spot_data.pop('_sa_instance_state', None)
    output.append(spot_data)
  return { 'data': output }

@app.route("/spots/add", methods=["POST"])
def add_spot():
  name = request.json.get('name')
  location_city = request.json.get('location_city')
  description = request.json.get('description')
  location_google = request.json.get('location_google')
  hero_img = request.json.get('hero_img')
  entry_map = request.json.get('entry_map')

  spot = Spot.query.filter(and_(Spot.name==name, Spot.location_city==location_city)).first()
  if spot:
    return 'Spot already exists', 409

  spot = Spot(
    name=name,
    location_city=location_city,
    description=description,
    location_google=location_google,
    hero_img=hero_img,
    entry_map=entry_map
  )
  db.session.add(spot)
  db.session.commit()
  return 'Done', 200

@app.route("/spots/patch", methods=["PATCH"])
def patch_spot():
  beach_id = request.json.get('id')
  spot = Spot.query.filter_by(id=beach_id).first()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(spot, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  spot_data = spot.__dict__
  spot_data.pop('_sa_instance_state', None)
  return spot_data, 200

@app.route("/review/add", methods=["POST"])
@jwt_required()
def add_review():
  user_id = get_jwt_identity()
  if user_id:
    user = get_current_user()
  if not user:
    email = request.json.get('email')
    user = User.query.filter_by(email=email).first()

  beach_id = request.json.get('beach_id')
  visibility = request.json.get('visibility')
  text = request.json.get('text')
  rating = request.json.get('rating')
  activity_type = request.json.get('activity_type')

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
    new_rating = ((spot.rating * spot.num_reviews) + rating) / (spot.num_reviews + 1)
    spot.rating = new_rating
    spot.num_reviews += 1
  spot.last_review_date = datetime.utcnow()
  spot.last_review_viz = visibility
  db.session.commit()
  return 'Done', 200

"""
Request
  {
    'beach_id': '1'
  }

Response
  {
    'data': [
      {

      }
    ]
  }
"""
@app.route("/review/get")
def get_reviews():
  beach_id = request.args.get('beach_id')

  reviews = Review.query.options(joinedload('user')).filter_by(beach_id=beach_id).all()
  output = []
  for review in reviews:
    spot_data = review.__dict__
    spot_data['user'] = review.user.__dict__
    spot_data['user'].pop('password', None)
    spot_data['user'].pop('_sa_instance_state', None)
    spot_data.pop('_sa_instance_state', None)
    output.append(spot_data)
  return { 'data': output }

