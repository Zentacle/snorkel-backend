import os
from flask import Blueprint, request
from app.models import Review, ShoreDivingReview
from app import cache, db
from sqlalchemy.orm import joinedload
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
  reviews = Review.query \
    .options(joinedload('spot')) \
    .order_by(Review.date_posted.desc()).limit(25).all()
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
  name='Mala Wharf'
  city_location='Lahaina, Maui'
  profile_pic='https://snorkel.s3.amazonaws.com/profile_pic/mjmayank.jpeg'
  display_name='Mayank Jain'
  formatted_date='March 2nd'
  hero_img='https://snorkel.s3.amazonaws.com/hero/puako_village_end.jpeg'
  text='This is my favorite scuba spot on the whole island. You are guaranteed to ...'
  beach_url='https://www.zentacle.com/Beach/1/mala-wharf'
  css = '''
  <style>
    .container {
      padding: 8px;
      margin-bottom: 8px;
    }

    .title {
      font-size: 20px;
      font-weight: 500;
      margin-bottom: 8px;
    }

    .metadataContainer {
      display: flex;
      margin-bottom: 8px;
      align-items: center;
    }

    .profilePicContainer {
      height: 16px;
      width: 16px;
    }

    .profilePicContainer {
      height: 16px;
      width: 16px;
      border-radius: 100%;
      overflow: hidden;
      margin-right: 2px;
    }

    .profilePic {
      height: 100%;
      width: 100%;
    }

    .stars {
      height: 16px;
      width: auto;
      margin: 0 4px;
    }

    .reviewContainer {
      display: flex;
    }

    .reviewTextContainer {
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }

    .reviewText {
      flex: 0 0 40px;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .heroImgContainer {
      flex: 0 0 80px;
      height: 78px;
      width: 78px;
      margin-right: 8px;
      overflow: hidden;
      border-radius: 8px;
    }

    .heroImg {
      height: 100%;
      width: 100%;
    }

    .seeMoreButton {
      background-color: #0087D3;
      border-radius: 32px;
      color: white;
      padding: 8px 4px;
      text-align: center;
      text-decoration: none;
    }
  </style>
  '''
  html = f'''
    <div class='container'>
    <div class='title'>{name} in {city_location}</div>
    <div class='metadataContainer'>
      <div class='profilePicContainer'>
        <img class='profilePic' src='{profile_pic}' />
      </div>
      <div>
        {display_name} -
      </div>
      <img class='stars' src='https://www.zentacle.com/_next/image?url=%2Ffullstar.png&w=64&q=75' />
      <div>
        on {formatted_date}
      </div>
    </div>
    <div class='reviewContainer'>
      <div class='heroImgContainer'>
        <img class='heroImg' src='{hero_img}' />
      </div>
      <div class='reviewTextContainer'>
        <div class='reviewText'>{text}</div>
        <a class='seeMoreButton' href='{beach_url}'>
          See more
        </a>
      </div>
    </div>
  </div>
  '''
  for x in range(3):
    html += html
  html += css
  message = Mail(
    from_email=('hello@zentacle.com', 'Zentacle'),
    to_emails='mayank@zentacle.com',
    subject='Recent activity on dive sites near you',
    html_content=html,
  )
  message.reply_to = 'mayank@zentacle.com'
  sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
  print(html)
  return 'ok'
  response = sg.send(message)
  return 'ok'
