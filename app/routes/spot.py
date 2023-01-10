import os
from flask import Blueprint, request
from app.models import Spot
from app import db, cache, get_summary_reviews_helper
import requests
from app.helpers.get_localities import get_localities

bp = Blueprint('spot', __name__, url_prefix="/spot")

@bp.route("/recalc", methods=["GET"])
def recalc_spot_rating():
  beach_id = request.args.get('beach_id')
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
  spot.id
  return { 'data': spot.get_dict() }

@bp.route("/setStationId", methods=["POST"])
def add_station_id():
  spot_id = request.json.get('spotId')
  station_id = request.json.get('stationId')
  spot = Spot.query.filter_by(id=spot_id).first_or_404()
  spot.noaa_station_id = station_id
  db.session.commit()
  spot.id
  return { 'data': spot.get_dict() }

@bp.route('/tide')
@cache.cached(query_string=True, timeout=3600)
def get_tides():
  station_id = request.args.get('station_id')
  begin_date = request.args.get('begin_date')
  end_date = request.args.get('end_date')
  endpoint = f'https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=predictions&begin_date={begin_date}&end_date={end_date}&datum=MLLW&station={station_id}&time_zone=GMT&units=english&interval=hilo&format=json&application=NOS.COOPS.TAC.TidePred'
  resp = requests.get(endpoint) \
    .json()
  return resp

@bp.route("/geocode")
def geocode():
    beach_id = request.args.get('id')
    spot = Spot.query.filter_by(id=beach_id).first_or_404()
    if not spot.latitude or not spot.longitude:
      return { 'msg': 'no lat/lng' }, 422
    r = requests.get('https://maps.googleapis.com/maps/api/geocode/json', params = {
      'latlng': f'{spot.latitude},{spot.longitude}',
      'key': os.environ.get('GOOGLE_API_KEY')
    })
    response = r.json()
    if response.get('status') == 'OK':
      address_components = response.get('results')[0].get('address_components')
      locality, area_2, area_1, country = get_localities(address_components)
      spot.locality = locality
      spot.area_one = area_1
      spot.area_two = area_2
      spot.country = country
      db.session.add(spot)
      db.session.commit()
      spot.id
    return spot.get_dict()