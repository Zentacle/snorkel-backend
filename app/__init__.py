from __future__ import print_function
from flask import Flask, request, jsonify
from flask.helpers import make_response
from flask_cors import CORS
import os
import os.path
import logging

from app.models import *
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_, not_
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
from app.helpers import create_account, login
import requests

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
if __name__ != '__main__':
  gunicorn_logger = logging.getLogger('gunicorn.error')
  app.logger.handlers = gunicorn_logger.handlers
  app.logger.setLevel(gunicorn_logger.level)
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
    users = None
    if request.args.get('real'):
      users = User.query.filter(
        and_(
          not_(User.email.contains('zentacle.com')),
          User.is_fake.is_not(True)
        )
      )
    else:
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
    return { 'msg': 'Wrong password or user does not exist' }, 400
  if bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
    return login(user)
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
  query = Spot.query
  if request.args.get('unverified'):
    query = query.filter(Spot.is_verified.isnot(True))
  else:
    query = query.filter(Spot.is_verified.isnot(False))
  query = query.order_by(sort)
  if request.args.get('limit') != 'none':
    query = query.limit(15)
  spots = query.all()
  output = []
  for spot in spots:
    spot_data = spot.get_dict()
    if request.args.get('ssg'):
      spot_data['beach_name_for_url'] = spot.get_beach_name_for_url()
    output.append(spot_data)
  return { 'data': output }

@app.route("/spots/search")
def search_spots():
  search_term = request.args.get('search_term')
  spots = Spot.query.filter(
    or_(
      Spot.name.ilike('%' + search_term + '%'),
      Spot.location_city.ilike('%'+ search_term + '%'),
      Spot.description.ilike('%'+ search_term + '%')
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
  place_id = request.json.get('place_id')
  user = get_current_user()
  is_verified = True if user and user.admin else False

  if not name or not location_city:
    return { 'msg': 'Please enter a name and location' }, 404

  spot = Spot.query.filter(and_(Spot.name==name, Spot.location_city==location_city)).first()
  if spot:
    return { 'msg': 'Spot already exists' }, 409

  if place_id and not location_google:
    r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params = {
      'place_id': place_id,
      'fields': 'name,geometry,address_components,url',
      'key': os.environ.get('GOOGLE_API_KEY')
    })
    response = r.json()
    if response.get('status') == 'OK':
      location_google = response.get('result').get('url')

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
  )
  db.session.add(spot)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  if not user or not user.admin:
    message = Mail(
        from_email=('no-reply@zentacle.com', 'Zentacle'),
        to_emails='mjmayank@gmail.com')

    message.template_id = 'd-df22c68e00c345108a3ac18ebf65bdaf'
    message.dynamic_template_data = {
        'beach_name': spot.name,
        'user_display_name': user.first_name,
        'description': description,
        'location': location_city,
    }
    if not os.environ.get('FLASK_ENV') == 'development':
      try:
          sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
          sg.send(message)
      except Exception as e:
          print(e.body)
  if user:
    message = Mail(
        from_email=('no-reply@zentacle.com', 'Zentacle'),
        to_emails=user.email,
        reply_to='mjmayank@gmail.com')

    message.template_id = 'd-2280f0af94dd4a93aea15c5ec95e1760'
    message.dynamic_template_data = {
        'beach_name': spot.name,
        'first_name': user.first_name,
        'url': spot.get_url(),
    }
    if not os.environ.get('FLASK_ENV') == 'development':
      try:
          sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
          sg.send(message)
      except Exception as e:
          print(e.body)
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
      if key == 'google_place_id':
        place_id = updates.get(key)
        if place_id == 'na':
          continue
        r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params = {
          'place_id': place_id,
          'fields': 'name,geometry,url',
          'key': os.environ.get('GOOGLE_API_KEY')
        })
        response = r.json()
        latitude = response.get('result').get('geometry').get('location').get('lat')
        longitude = response.get('result').get('geometry').get('location').get('lng')
        url = response.get('result').get('url')
        spot.latitude = latitude
        spot.longitude = longitude
        spot.location_google = url
  except ValueError as e:
    return e, 500
  db.session.commit()
  spot.id
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
      from_email=('no-reply@zentacle.com', 'Zentacle'),
      to_emails='mjmayank@gmail.com')

  message.template_id = 'd-3188c5ee843443bf91c5eecf3b66f26d'
  message.dynamic_template_data = {
      'beach_name': spot.name,
      'first_name': user.first_name,
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
  limit = request.args.get('limit')
  offset = int(request.args.get('offset')) if request.args.get('offset') else 0

  query = Review.query.options(joinedload('user')).options(joinedload('shorediving_data')).options(joinedload('images')).order_by(Review.date_posted.desc()).filter_by(beach_id=beach_id)
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
    for image in review.images:
      image_data.append(image.get_dict())
    data['images'] = image_data
    output.append(data)
  return { 'data': output, 'next_offset': offset + len(output) }

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

@app.route("/review/patch", methods=["PATCH"])
def patch_review():
  beach_id = request.json.get('id')
  spot = Review.query.filter_by(id=beach_id).first()
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

@app.route("/review/delete")
def delete_review():
  review_id = request.args.get('review_id')

  review = Review.query.filter_by(id=review_id).first()
  beach_id = review.beach_id
  rating = review.rating
  for image in review.images:
    Image.query.filter_by(id=image.id).delete()

  if review.shorediving_data:
    ShoreDivingReview.query.filter_by(id=review.shorediving_data.id).delete()

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
    .filter(Spot.is_verified.isnot(False)) \
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
      dictionary['signedurl'] = create_presigned_url_local('reviews/' + dictionary['url'])
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

def create_presigned_url_local(filename, expiration=3600):
    """Generate a presigned URL to share an S3 object
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """
    bucket_name = "snorkel"
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
    bucket_name = 'snorkel'
    object_name = request.args.get('file')
    expiration=3600

    # Generate a presigned S3 POST URL
    s3_client = boto3.client('s3', region_name='us-east-1')
    try:
        response = s3_client.generate_presigned_post(Bucket=bucket_name,
                                                     Key=object_name,
                                                     ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL and required fields
    return response

@app.route("/user/get")
def get_user():
    username = request.args.get('username')
    user = User.query \
      .options(joinedload('reviews')) \
      .filter_by(username=username).first()
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
  beach_id = request.json.get('beach_id')
  reviews = request.json.get('data')

  for review_json in reviews:
    username = review_json.get('username')
    user = User.query.filter_by(username=username).first()
    display_name = review_json.get('display_name')
    first_name = review_json.get('first_name')
    if not user:
      user = User(
        username=username,
        display_name=display_name,
        first_name=first_name,
        email='noreply+'+username+'@zentacle.com',
      )
      db.session.add(user)
      db.session.commit()

    visibility = review_json.get('visibility') if review_json.get('visibility') != '' else None
    text = review_json.get('text')
    rating = review_json.get('rating')
    activity_type = review_json.get('activity_type')
    date_posted = dateutil.parser.isoparse(review_json.get('date_dived'))
    date_dived = dateutil.parser.isoparse(review_json.get('date_dived')) if review_json.get('date_dived') else datetime.utcnow()
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
      date_posted=date_posted,
    )

    shorediving_data = ShoreDivingReview(
      shorediving_url=review_json.get('shorediving_url'),
      shorediving_id=review_json.get('shorediving_id'),
      review=review,
    )

    db.session.add(review)
    db.session.add(shorediving_data)

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
    review.id
  return { 'msg': 'all done' }, 200

@app.route("/spot/recalc", methods=["POST"])
def recalc_spot_rating():
  beach_id = request.json.get('beach_id')
  summary = get_summary_reviews_helper(beach_id)
  return {}

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

@app.route("/spots/nearby")
def nearby_locations():
  beach_id = request.args.get('beach_id')
  spot = Spot.query.filter_by(id=beach_id).first_or_404()
  startlat = spot.latitude
  startlng = spot.longitude
  if not startlat or not startlng:
    return { 'msg': 'No lat/lng for this spot ' }, 400
  query = "SELECT id, name, hero_img, rating, num_reviews, location_city, SQRT(POW(69.1 * (latitude - %(startlat)s), 2) + POW(69.1 * (%(startlng)s - longitude) * COS(latitude / 57.3), 2)) AS distance FROM spot WHERE id != %(beach_id)s AND is_verified=true ORDER BY distance LIMIT 10;" % {'startlat':startlat, 'startlng':startlng, 'beach_id':beach_id}
  # used for testing locally on sqlite since it doesn't support any of the math functions in sql
  # query = "SELECT id, name, hero_img, rating, num_reviews, location_city, %(startlng)s + %(startlat)s AS distance FROM spot WHERE latitude is NOT NULL AND longitude is NOT NULL ORDER BY distance LIMIT 10;" % {'startlat':startlat, 'startlng':startlng}
  results = db.engine.execute(query)
  data = []
  for id, name, hero_img, rating, num_reviews, location_city, distance in results:
    data.append({
      'id': id,
      'name': name,
      'hero_img': hero_img,
      'rating': rating,
      'num_reviews': num_reviews,
      'distance': distance,
      'location_city': location_city,
      'url': Spot.create_url(id, name),
    })
  return { 'data': data }

@app.route("/spots/location")
def get_location_spots():
  type = request.args.get('type')
  name = request.args.get('name')
  locality = None
  if type == 'locality':
    locality = Locality.query.filter_by(name=name).first()
  if type == 'area_one':
    locality = AreaOne.query.filter_by(name=name).first()
  if type == 'area_two':
    locality = AreaTwo.query.filter_by(name=name).first()
  if type == 'country':
    locality = Country.query.filter_by(name=name).first()
  data = []
  for spot in locality.spots:
    data.append(spot.get_dict())
  return { 'data': data }

@app.route("/locality/locality")
def get_localities():
  localities = Locality.query.all()
  data = []
  for locality in localities:
    data.append(locality.get_dict())
  return { 'data': data }

@app.route("/locality/area_two")
def get_area_two():
  localities = AreaTwo.query.all()
  data = []
  for locality in localities:
    data.append(locality.get_dict())
  return { 'data': data }

@app.route("/locality/area_one")
def get_area_one():
  localities = AreaOne.query.all()
  data = []
  for locality in localities:
    data.append(locality.get_dict())
  return { 'data': data }

@app.route("/locality/country")
def get_country():
  localities = Country.query.all()
  data = []
  for locality in localities:
    data.append(locality.get_dict())
  return { 'data': data }

@app.route("/loc/country/patch", methods=["PATCH"])
def patch_country():
  id = request.json.get('id')
  user = Country.query.filter_by(id=id).first()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(user, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  return user.get_dict(), 200

@app.route("/loc/area_one/patch", methods=["PATCH"])
def patch_loc():
  id = request.json.get('id')
  user = AreaOne.query.filter_by(id=id).first()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(user, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  return user.get_dict(), 200

@app.route("/locality/<country>/<area_one>")
def get_wildcard_locality(country, area_one):
  locality = AreaOne.query.filter(and_(AreaOne.short_name==area_one, AreaOne.country.has(short_name=country))).first()
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
        locality_name = None
        area_1_name = None
        area_2_name = None
        country_name = None
        for component in address_components:
          if 'locality' in component.get('types'):
            locality_name = component.get('long_name')
          if 'administrative_area_level_1' in component.get('types'):
            area_1_name = component.get('long_name')
          if 'administrative_area_level_2' in component.get('types'):
            area_2_name = component.get('long_name')
          if 'country' in component.get('types'):
            country_name = component.get('long_name')
        country = Country.query.filter_by(name=country_name).first()
        if not country:
          country = Country(
            name=country_name
          )
        area_1 = AreaOne.query.filter_by(name=area_1_name).first()
        if not area_1:
          area_1 = AreaOne(
            name=area_1_name,
            country=country,
          )
        area_2 = AreaTwo.query.filter_by(name=area_2_name).first()
        if not area_2:
          area_2 = AreaTwo(
            name=area_2_name,
            area_one=area_1,
            country=country,
          )
        locality = Locality.query.filter_by(name=locality_name).first()
        if not locality:
          locality = Locality(
            name=locality_name,
            area_one=area_1,
            area_two=area_2,
            country=country,
          )
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