from flask import Blueprint, request
from app.models import User, Review
from sqlalchemy import and_, not_
from app import cache, db

bp = Blueprint('users', __name__, url_prefix="/users")

@bp.route("/nearby")
def users_nearby():
  latitude = request.args.get('latitude')
  longitude = request.args.get('longitude')
  query = User.query.filter(User.latitude.is_not(None)).order_by(User.distance(latitude, longitude)).limit(10)
  results = query.all()
  return { 'data': [result.get_dict() for result in results] }

@bp.route("/all")
@cache.cached(query_string=True)
def getAllData():
    users = None
    if request.args.get('top'):
      users = db.session.query(
          User,
          db.func.count(User.reviews).label('num_reviews')
        ) \
        .join(Review) \
        .group_by(User) \
        .order_by(db.text('num_reviews DESC')) \
        .limit(10)
    elif request.args.get('real'):
      users = User.query \
        .filter(
          and_(
            not_(User.email.contains('zentacle.com')),
            User.is_fake.is_not(True),
            User.email.is_not(None)
          )
        )
      output = []
      for user in users:
        data = user.get_dict()
        output.append(data)
      return { 'data': output, 'count': len(output) }
    else:
      users = db.session.query(
          User,
          db.func.count(User.reviews).label('num_reviews')
        ) \
        .join(Review) \
        .group_by(User) \
        .all()
    output = []
    for user, num_reviews in users:
      data = user.get_dict()
      data['num_reviews'] = num_reviews
      output.append(data)
    return { 'data': output }