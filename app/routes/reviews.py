import os
from flask import Blueprint, request
from app.models import Review, ShoreDivingReview
from app import cache, db
from sqlalchemy.orm import joinedload
from flask_jwt_extended import jwt_required, get_current_user

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