from flask import Blueprint, request
from app.models import User

bp = Blueprint('users', __name__, url_prefix="/users")

@bp.route("/nearby")
def users_nearby():
  latitude = request.args.get('latitude')
  longitude = request.args.get('longitude')
  query = User.query.filter(User.latitude.is_not(None)).order_by(User.distance(latitude, longitude)).limit(10)
  results = query.all()
  return { 'data': [result.get_dict() for result in results] }