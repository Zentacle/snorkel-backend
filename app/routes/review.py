import os
import logging
import boto3
import io
import requests
from flask import Blueprint, request
from app.models import (
  Review,
  Spot,
  User,
  ShoreDivingData,
  ShoreDivingReview,
  Image,
  DiveShop
)
from app import (
  db,
  get_summary_reviews_helper,
  fake_users
)
from flask_jwt_extended import (
  jwt_required,
  get_current_user,
  get_jwt_identity
)
from app.helpers.validate_email_format import validate_email_format
import dateutil.parser
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sqlalchemy.orm import joinedload
from sqlalchemy import and_
from app.helpers.demicrosoft import demicrosoft

bp = Blueprint('review', __name__, url_prefix="/review")
wally_api_base = os.environ.get('WALLY_API')
wally_auth_token = os.environ.get('WALLY_AUTH_TOKEN')

@bp.route("/add", methods=["POST"])
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
  dive_shop_id = request.json.get('dive_shop_id')
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
    dive_shop_id=dive_shop_id
  )

  for image in images:
    try:
      image = Image(
        url=image,
        beach_id=beach_id,
        user_id=user.id,
      )
      review.images.append(image)
    except Exception as e:
      print(e.body)

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

  wallet_id = ''
  if request.json.get('include_wallet'):
    request_url = f'{wally_api_base}/wallets/create'
    headers = {
      'Authorization': f'Bearer {wally_auth_token}',
      'Content-Type': 'application/json',
    }

    payload = {
      'id': f'user_{str(user.id)}',
      'email': user.email, # owner is the current user, so owner email is current user email
      'tags': ['user']
    }

    response = requests.post(request_url, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    wallet_id = data.get('id')

  message = Mail(
      from_email=('hello@zentacle.com', 'Zentacle'),
      to_emails='mayank@zentacle.com')

  message.template_id = 'd-3188c5ee843443bf91c5eecf3b66f26d'
  message.reply_to = user.email
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

  if request.json.get('include_wallet'):
    if dive_shop_id:
      dive_shop = DiveShop.query.get_or_404(dive_shop_id)
      if dive_shop.stamp_uri:
        headers = {
          'Authorization': f'Bearer {wally_auth_token}',
          'Content-Type': 'application/json',
        }

        payload = {
          "uri": dive_shop.stamp_uri,
          "walletId": wallet_id
        }

        nft_request_url = f'{wally_api_base}/nfts/create/from-uri'
        nft_response = requests.post(nft_request_url, json=payload, headers=headers)
        nft_response.raise_for_status()
  
  return { 'review': review.get_dict(), 'spot': spot.get_dict() }, 200

@bp.route("/get")
def get_review():
  """ Get Review
  ---
  get:
      summary: Get Single Review
      description: Get Single Review
      parameters:
          - name: review_id
            in: body
            description: review_id
            type: integer
            required: true
      responses:
          200:
              description: Returns review object
              content:
                application/json:
                  schema: ReviewSchema
  """
  review_id = request.args.get('review_id')
  if review_id:
    review = Review.query.filter_by(id=review_id).first()
    spot = review.spot
    data = review.get_dict()
    dive_shop = {}
    if review.dive_shop:
      dive_shop = review.dive_shop.get_dict()
    data['user'] = review.user.get_dict()
    return { 'review': data, 'spot': spot.get_dict(), 'dive_shop': dive_shop }
  else:
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
        signedUrls.append(image.url)
      data['images'] = image_data
      data['signedUrls'] = signedUrls
      output.append(data)
    return { 'data': output, 'next_offset': offset + len(output) }

# returns count for each rating for individual beach/area ["1"] ["2"] ["3"], etc
# returns count for total ratings ["total"]
# returns average rating for beach ["average"]
@bp.route("/getsummary")
def get_summary_reviews():
  return {"data": get_summary_reviews_helper(request.args.get('beach_id'))}

@bp.route("/patch", methods=["PATCH"])
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
          - name: date_dived
            in: body
            description: date and time of dive in UTC format
            type: string
            required: false
          - name: dive_length
            in: body
            description: amount of time in water (in minutes)
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
  if "date_dived" in updates:
    updates['date_dived'] = dateutil.parser.isoparse(request.json.get('date_dived'))
  updates.pop('id', None)
  updates.pop('date_posted', None)
  try:
    for key in updates.keys():
      setattr(spot, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  spot_data = spot.get_dict()
  return spot_data, 200

@bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_file():
    """ Upload File
    ---
    post:
        summary: Upload a file so that it can be attached to a review
        description: Upload a file so that it can be attached to a review (one at a time)
        requestBody:
            content:
              multipart/form-data:
                schema: ImageUploadRequestSchema
        responses:
            200:
                description: Returns the url of the s3 upload
                content:
                  application/json:
                    schema: ImageUploadResponseSchema
    """
    # check if the post request has the file part
    if 'file' not in request.files:
        return { 'msg': 'No file included in request' }, 422
    files = request.files.getlist('file')
    s3_url = ''
    file_urls = []
    for file in files:
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            return { 'msg': 'Submitted an empty file' }, 422
        import uuid
        s3_key = str(get_current_user().id) + '_' + str(uuid.uuid4())
        contents = file.read()
        bucket = os.environ.get('S3_BUCKET_NAME')
        logging.error (f"Content Type {file.content_type}")
        s3_url = boto3.client("s3").upload_fileobj(io.BytesIO(contents), bucket, 'reviews/'+s3_key,
                                  ExtraArgs={'ACL': 'public-read',
                                              'ContentType': file.content_type}
                                  )
        s3_url = f'https://{bucket}.s3.amazonaws.com/reviews/{s3_key}'
        file_urls.append(s3_url)
    return { 'data': file_urls }

@bp.route("/delete", methods=["POST"])
@jwt_required()
def delete_review():
  review_id = request.args.get('review_id')
  keep_images = request.args.get('keep_images')

  user = get_current_user()
  review = Review.query \
    .filter_by(id=review_id) \
    .options(joinedload(Review.images)) \
    .first_or_404()
  if review.author_id != user.id and not user.admin:
    return {'msg': 'You are not allowed to do that'}, 403
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

@bp.route("/fake", methods=["POST"])
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

@bp.route("/add/shorediving", methods=["POST"])
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