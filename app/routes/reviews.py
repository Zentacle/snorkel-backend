import os
import datetime
from flask import Blueprint, request
from app.models import Review, ShoreDivingReview, Spot
from app import cache, db
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from flask_jwt_extended import jwt_required, get_current_user
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

bp = Blueprint('reviews', __name__, url_prefix="/reviews")

@bp.route("/recent")
def get_recent_reviews():
  """ Get Recent Reviews
  ---
  get:
      summary: Get recent reviews
      description: Get recent reviews
      responses:
          200:
              description: Returns review object
              content:
                application/json:
                  schema: ReviewSchema
  """
  limit = request.args.get('limit') if request.args.get('limit') else 25
  offset = request.args.get('offset') if request.args.get('offset') else 0
  latitude = request.args.get('latitude')
  longitude = request.args.get('longitude')
  reviews = Review.query \
    .options(joinedload('spot'))
  if request.args.get('type') == 'nearby' and latitude:
    nearby_spots = db.session.query(Spot.id) \
      .filter(Spot.distance(latitude, longitude) < 50).subquery()
    reviews = reviews.filter(Review.beach_id.in_(nearby_spots))

  reviews = reviews.order_by(Review.date_posted.desc()) \
    .limit(limit) \
    .offset(offset) \
    .all()
  data = []
  for review in reviews:
    spot = review.spot
    review_data = review.get_dict()
    review_data['spot'] = spot.get_dict()
    data.append(review_data)
  return { 'data': data }

@bp.route("/get")
@cache.cached(query_string=True)
def get_reviews():
  """ Get Reviews
  ---
  get:
      summary: Get Reviews for spot
      description: Get Reviews for spot
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
      signedUrls.append(image.url)
    data['images'] = image_data
    data['signedUrls'] = signedUrls
    output.append(data)
  return { 'data': output, 'next_offset': offset + len(output) }

@bp.route("/delete", methods=["POST"])
@jwt_required()
def delete_shore_diving_ids():
  user = get_current_user()
  if not user.admin:
    return {'msg': 'You must be an admin to that'}, 403
  id = request.json.get('id')
  sd_review = ShoreDivingReview.query.filter_by(shorediving_id=id).first_or_404()
  review = sd_review.review
  db.session.delete(sd_review)
  db.session.delete(review)
  db.session.commit()
  return 'ok'

@bp.route("/recentemail")
def send_recent_reviews():
  date = datetime.datetime.now() - datetime.timedelta(days=7)
  date_str=datetime.date.strftime(date, "%m-%d-%Y") if not request.args.get('date') else request.args.get('date')
  reviews = Review.query \
    .options(joinedload('user')) \
    .options(joinedload('spot')) \
    .filter(Review.text.is_not(None)) \
    .filter(Review.date_posted > date_str) \
    .order_by(func.length(Review.text).desc()).limit(10).all()
  one_star = '''
    <img style='height: 16px;width: auto;margin: 0 4px;' src='https://www.zentacle.com/_next/image?url=%2Ffullstar.png&w=64&q=75' />
  '''
  stars = ''
  for x in range(5):
    stars += one_star
  first_name='Mayank'
  intro = f'''
    <div style='padding: 0 8px'>Hi {first_name},</div>
    <div style='padding: 0 8px'>Check out the most recent reviews and dive logs posted on Zentacle!</div>
  '''
  html = intro
  for review in reviews:
    name=review.spot.name
    city_location=review.spot.location_city
    profile_pic=review.user.profile_pic
    display_name=review.user.display_name
    formatted_date=datetime.date.strftime(review.date_posted, "%B %d")
    hero_img=review.spot.hero_img
    text=review.text
    beach_url=f'https://www.zentacle.com{review.spot.get_url()}'
    post = f'''
      <div style='padding: 8px;margin-bottom: 8px;'>
      <a href='{beach_url}' style='font-size: 20px;font-weight: 500;margin-bottom: 8px;text-decoration:none'>{name} in {city_location}</a>
      <div style='display: flex;margin-bottom: 8px;align-items: center;'>
        <div style='height: 16px;width: 16px;border-radius: 100%;overflow: hidden;margin-right: 2px;'>
          <img style='height: 100%;width: 100%;' src='{profile_pic}' />
        </div>
        <div>
          {display_name} -
        </div>
        {stars}
        <div>
          on {formatted_date}
        </div>
      </div>
      <div style='display: flex;'>
        <a href='{beach_url}' style='flex: 0 0 80px;height: 78px;width: 78px;margin-right: 8px;overflow: hidden;border-radius: 8px;'>
          <img style='height: 100%;width: 100%;' src='{hero_img}' />
        </a>
        <div>
          <div style='flex: 0 0 40px;overflow: hidden;text-overflow: ellipsis;margin-bottom: 8px;'>{text}</div>
          <a style='background-color: #0087D3;border-radius: 32px;color: white;padding: 8px 16px;text-align: center;text-decoration: none;' href='{beach_url}'>
            See more
          </a>
        </div>
      </div>
    </div>
    '''
    html += post
  message = Mail(
    from_email=('hello@zentacle.com', 'Zentacle'),
    to_emails='mayank@zentacle.com',
    subject='Recent activity on dive sites near you',
    html_content=html,
  )
  message.reply_to = 'mayank@zentacle.com'
  sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
  print(html)
  return {'data': html.replace('\n', '')}
  # response = sg.send(message)
  return 'ok'
