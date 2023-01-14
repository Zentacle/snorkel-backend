from sqlalchemy import and_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload

from app.models import Spot

def get_nearby_spots(latitude, longitude, limit=25, spot_id=None):
  limit = limit if limit else 25
  try:
    query = Spot.query.filter(and_(
      Spot.is_verified == True,
      Spot.is_deleted.is_not(True),
      Spot.id != spot_id,
    )).options(joinedload('locality')).order_by(Spot.distance(latitude, longitude)).limit(limit)
    return query.all()
  except OperationalError as e:
    if "no such function: sqrt" in str(e).lower():
      query = Spot.query.filter(and_(
        Spot.is_verified == True,
        Spot.is_deleted.is_not(True),
        Spot.id != spot_id,
      )).options(joinedload('locality')).order_by(Spot.sqlite3_distance(latitude, longitude)).limit(limit)
      return query.all()
    else:
      raise e
  except Exception as e:
    raise e