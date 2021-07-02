from __future__ import print_function
from flask import Flask, request, redirect, url_for, session, jsonify, render_template
from flask_cors import CORS
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os.path
from app.models import *

app = Flask(__name__)
app.secret_key = 'the random string'
SQLALCHEMY_DATABASE_URI = (os.environ.get('DATABASE_URL').replace("://", "ql://", 1)
  if not os.environ.get('FLASK_ENV') == 'development'
  else os.environ.get('DATABASE_URL'))
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

cors = CORS(app)
db.init_app(app)

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
      output.append({
        'email': user.email,
        'video_id': user.video_id,
        'is_processed': user.is_processed,
      })
    return { 'data': output }

"""
  ?email=mjmayank@gmail.com
"""
@app.route('/test', methods=["GET"])
def get_user_videos():
  email = request.args.get('email')
  users = User.query.filter_by(email=email).all()
  output = []
  for user in users:
    output.append({
      'email': user.email,
      'video_id': user.video_id,
      'is_processed': user.is_processed,
    })
  return { 'data': output }

@app.route("/user/signup")
def get_spots():
  display_name = request.json.get('display_name')
  email = request.json.get('email')
  username = request.json.get('username')
  profile_pic = request.json.get('profile_pic')

  user = User(
    display_name=display_name,
    email=email,
    username=username,
    profile_pic=profile_pic
  )
  db.session.add(user)
  db.session.commit()
  return 'Done', user.id

@app.route("/spots/get")
def get_spots():
  users = Spot.query.all()
  output = []
  for spot in users:
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

  spot = Spot(
    name=name,
    location_city=location_city,
    description=description,
    location_google=location_google,
    hero_img=hero_img
  )
  db.session.add(spot)
  db.session.commit()
  return 'Done', 200

@app.route("/review/add", methods=["POST"])
def add_review():
  # token = request.json.get('token')
  # idinfo = id_token.verify_oauth2_token(token, Request(), CLIENT_ID)
  # email = idinfo['email']
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

  spot = Spot.query.filter_by(beach_id=beach_id).all()
  new_rating = ((spot.rating * spot.num_ratings) + rating) / (spot.num_ratings + 1)
  spot.rating = new_rating
  spot.num_ratings += 1
  db.session.commit()
  return 'Done', 200

@app.route("/review/get")
def get_reviews():
  beach_id = request.json.get('beach_id')

  reviews = Spot.query.filter_by(beach_id=beach_id).all()
  output = []
  for review in reviews:
    spot_data = review.__dict__
    spot_data.pop('_sa_instance_state', None)
    output.append(spot_data)
  return { 'data': output }

