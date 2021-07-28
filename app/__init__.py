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
from flask_migrate import Migrate
import dateutil.parser
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

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
      output.append(user.get_dict())
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
    return { 'msg': 'An account with this email already exists' }, 400
  user = User.query.filter_by(username=username).first()
  if user:
    return { 'msg': 'An account with this username already exists' }, 400

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
  message = Mail(
      from_email=('no-reply@straightshotvideo.com', 'Zentacle'),
      to_emails='mjmayank@gmail.com')

  message.template_id = 'd-926fe53d5696480fb65b92af8cd8484e'
  message.dynamic_template_data = {
      'display_name': display_name,
      'username': username,
      'email': email,
  }
  if not os.environ.get('FLASK_ENV') == 'development':
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        print(e.body)
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
    return { 'msg': 'Wrong password or user does not exist' }, 400
  if bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
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
  else:
    return { 'msg': 'Wrong password or user does not exist' }, 400

@app.route("/user/patch", methods=["PATCH"])
def patch_user():
  user_id = request.json.get('id')
  user = User.query.filter_by(id=user_id).first()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(user, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  return user.get_dict(), 200

@app.route("/user/me")
@jwt_required(refresh=True)
def get_me():
    user = get_current_user()
    resp = make_response(user.get_dict())
    auth_token = create_access_token(identity=user.id)
    set_access_cookies(resp, auth_token)
    return resp

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
    spot_data = spot.get_dict()
    spot_data["ratings"] = get_summary_reviews_helper(beach_id)
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
  query = Spot.query.filter(Spot.is_verified.isnot(False)).order_by(sort)
  if request.args.get('limit') != 'none':
    query = query.limit(15)
  spots = query.all()
  output = []
  for spot in spots:
    spot_data = spot.get_dict()
    output.append(spot_data)
  return { 'data': output }

@app.route("/spots/search")
def search_spots():
  search_term = request.args.get('search_term')
  spots = Spot.query.filter(
    or_(
      Spot.name.ilike('%' + search_term + '%'), \
      Spot.location_city.ilike('%'+ search_term + '%')
    )
  ).all()
  output = []
  for spot in spots:
    spot_data = spot.get_dict()
    output.append(spot_data)
  return { 'data': output }

@app.route("/spots/add", methods=["POST"])
@jwt_required(optional=True)
def add_spot():
  name = request.json.get('name')
  location_city = request.json.get('location_city')
  description = request.json.get('description')
  location_google = request.json.get('location_google')
  hero_img = request.json.get('hero_img')
  entry_map = request.json.get('entry_map')
  is_verified = True if get_current_user() and get_current_user().admin else False

  if not name or not location_city:
    return { 'msg': 'Please enter a name and location' }, 404

  spot = Spot.query.filter(and_(Spot.name==name, Spot.location_city==location_city)).first()
  if spot:
    return { 'msg': 'Spot already exists' }, 409

  spot = Spot(
    name=name,
    location_city=location_city,
    description=description,
    location_google=location_google,
    hero_img=hero_img,
    entry_map=entry_map,
    is_verified=is_verified,
  )
  db.session.add(spot)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  return { 'data': spot.get_dict() }, 200

@app.route("/spots/patch", methods=["PATCH"])
@jwt_required()
def patch_spot():
  if not get_current_user().admin:
    return { 'msg': "Only admins can do that" }, 401
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
  spot_data = spot.get_dict()
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
  visibility = request.json.get('visibility') if request.json.get('visibility') != '' else None
  text = request.json.get('text')
  rating = request.json.get('rating')
  activity_type = request.json.get('activity_type')
  imageURLs = request.json.get('images') or []
  date_dived = dateutil.parser.isoparse(request.json.get('date_dived')) if request.json.get('date_dived') else datetime.utcnow()
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
    date_dived=date_dived,
  )

  for imageURL in imageURLs:
    image = Image(
      url=imageURL,
      beach_id=beach_id,
      user_id=user.id,
    )
    review.images.append(image)

  db.session.add(review)

  spot = Spot.query.filter_by(id=beach_id).first()
  if not spot:
    return { 'msg': 'Couldn\'t find that spot' }, 404
  if not spot.num_reviews:
    spot.num_reviews = 1
    spot.rating = rating
  else:
    new_rating = str(round(((float(spot.rating) * (spot.num_reviews*1.0)) + rating) / (spot.num_reviews + 1), 2))
    spot.rating = new_rating
    spot.num_reviews += 1
  if visibility and (not spot.last_review_date or date_dived > spot.last_review_date):
    spot.last_review_date = date_dived
    spot.last_review_viz = visibility
  db.session.commit()
  message = Mail(
      from_email=('no-reply@straightshotvideo.com', 'Zentacle'),
      to_emails='mjmayank@gmail.com')

  message.template_id = 'd-3188c5ee843443bf91c5eecf3b66f26d'
  message.dynamic_template_data = {
      'beach_name': spot.name,
      'display_name': user.display_name,
      'text': text,
      'url': 'https://www.zentacle.com/'+str(beach_id),
  }
  if not os.environ.get('FLASK_ENV') == 'development':
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        print(e.body)
  review.id
  return { 'data': review.get_dict() }, 200

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

  reviews = Review.query.options(joinedload('user')).order_by(Review.date_posted.desc()).filter_by(beach_id=beach_id).all()
  output = []
  for review in reviews:
    data = review.get_dict()
    data['user'] = review.user.get_dict()
    output.append(data)
  return { 'data': output }

# returns count for each rating for individual beach/area ["1"] ["2"] ["3"], etc
# returns count for total ratings ["total"]
# returns average rating for beach ["average"]
@app.route("/review/getsummary")
def get_summary_reviews():
  return {"data": get_summary_reviews_helper(request.args.get('beach_id'))}

def get_summary_reviews_helper(beach_id):
  reviews = db.session.query(db.func.count(Review.rating), Review.rating).filter_by(beach_id=beach_id).group_by(Review.rating).all()
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

@app.route("/review/delete")
def delete_review():
  review_id = request.args.get('review_id')

  review = Review.query.filter_by(id=review_id).first()
  beach_id = review.beach_id
  rating = review.rating

  spot = Spot.query.filter_by(id=beach_id).first()
  if spot.num_reviews == 1:
    spot.num_reviews = 0
    spot.rating = None
  else:
    new_rating = str(round(((float(spot.rating) * (spot.num_reviews*1.0)) - rating) / (spot.num_reviews - 1), 2))
    spot.rating = new_rating
    spot.num_reviews -= 1
  Review.query.filter_by(id=review_id).delete()
  db.session.commit()
  return {}

@app.route("/spots/recs")
@jwt_required(optional=True)
def get_recs():
  user_id = get_jwt_identity()
  if not user_id:
    return { 'data': {} }, 401
  # (SELECT * FROM SPOT a LEFT JOIN REVIEW b ON a.id = b.beach_id WHERE b.author_id = user_id) as my_spots
  # SELECT * FROM SPOT A LEFT JOIN my_spots B ON A.id = B.id WHERE b.id IS NULL
  spots_been_to = db.session.query(Spot.id).join(Review, Spot.id == Review.beach_id, isouter=True).filter(Review.author_id==user_id).subquery()
  spots = Spot.query \
    .filter(Spot.id.not_in(spots_been_to)) \
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
    username = random.choice(fake_users)
    user = User.query.filter_by(display_name=username).first()
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
  email = username + '@zentacle.com'
  unencrypted_password = 'password'
  password = bcrypt.hashpw(unencrypted_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

  user = User.query.filter_by(display_name=display_name).first()
  if user:
    return { 'msg': 'A fake account with this name already exists' }, 400

  user = User(
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

@app.route("/images")
def get_images():
    images = Image.query.all()
    output = []
    for image in images:
      output.append(image.get_dict())
    return { 'data': output }
