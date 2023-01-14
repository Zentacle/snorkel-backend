import requests
import os
from flask import Blueprint, request
import newrelic.agent
from sqlalchemy import or_

from app import cache
from app.models import (
  Spot,
  Country,
  AreaOne,
  AreaTwo,
  Locality
)
from app.helpers.get_nearby_spots import get_nearby_spots
from app.helpers.typeahead_from_spot import typeahead_from_spot

bp = Blueprint('search', __name__, url_prefix="/search")

@bp.route("/location")
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

@bp.route("/autocomplete")
def search_autocomplete():
  search_term = request.args.get('q')
  spots = Spot.query.filter(
    Spot.name.ilike('%' + search_term + '%')
  ).limit(5).all()
  output = []
  for spot in spots:
    spot_data = {
      'label': spot.name,
      'type': 'spot',
      'url': spot.get_url(),
    }
    output.append(spot_data)
  return { 'data': output }

@bp.route("/typeahead")
@cache.cached(query_string=True)
def get_typeahead():
  """ Search Typeahead
  ---
  get:
      summary: Typeahead locations for search bar
      description: Typeahead locations for search bar
      parameters:
          - name: query
            in: query
            description: query
            type: string
            required: true
          - name: beach_only
            in: query
            description: should only return beach spots. ie ?beach_only=True
            type: string
            required: false
      responses:
          200:
              description: Returns list of typeahead objects
              content:
                application/json:
                  schema: TypeAheadSchema
  """
  newrelic.agent.capture_request_params()
  query = request.args.get('query')
  beach_only = request.args.get('beach_only')
  results = []
  spots = Spot.query \
    .filter(
      or_(
        Spot.name.ilike('%'+query+'%'),
        Spot.location_city.ilike('%'+ query + '%'),
      )
    ) \
    .filter(Spot.is_deleted.is_not(True)) \
    .limit(25) \
    .all()
  for spot in spots:
    result = typeahead_from_spot(spot)
    results.append(result)
  if beach_only:
    return { 'data': results }

  countries = Country.query.filter(Country.name.ilike('%'+query+'%')).limit(10).all()
  area_ones = AreaOne.query.filter(AreaOne.name.ilike('%'+query+'%')).limit(10).all()
  area_twos = AreaTwo.query.filter(AreaTwo.name.ilike('%'+query+'%')).limit(10).all()
  localities = Locality.query.filter(Locality.name.ilike('%'+query+'%')).limit(10).all()
  for loc in countries:
    url = loc.get_url()
    segments = url.split("/")
    country = segments[2]
    area_one = None
    area_two = None
    locality = None
    if len(segments) > 3:
      area_one = segments[3]
    if len(segments) > 4:
      area_two = segments[4]
    if len(segments) > 5:
      locality = segments[5]
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': url,
      'type': 'location',
      'subtext': loc.name,
      'data': {
        'country': country,
        'area_one': area_one,
        'area_two': area_two,
        'locality': locality
      }
    }
    results.append(result)
  for loc in area_ones:
    url = loc.get_url(loc.country)
    segments = url.split("/")
    country = segments[2]
    area_one = None
    area_two = None
    locality = None
    if len(segments) > 3:
      area_one = segments[3]
    if len(segments) > 4:
      area_two = segments[4]
    if len(segments) > 5:
      locality = segments[5]
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': url,
      'type': 'location',
      'subtext': loc.country.name,
      'data': {
        'country': country,
        'area_one': area_one,
        'area_two': area_two,
        'locality': locality
      }
    }
    results.append(result)
  for loc in area_twos:
    url = loc.get_url(loc.country, loc.area_one)
    segments = url.split("/")
    country = segments[2]
    area_one = None
    area_two = None
    locality = None
    if len(segments) > 3:
      area_one = segments[3]
    if len(segments) > 4:
      area_two = segments[4]
    if len(segments) > 5:
      locality = segments[5]
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': url,
      'type': 'location',
      'subtext': loc.country.name,
      'data': {
        'country': country,
        'area_one': area_one,
        'area_two': area_two,
        'locality': locality
      }
    }
    results.append(result)
  for loc in localities:
    url = loc.get_url(loc.country, loc.area_one, loc.area_two)
    segments = url.split("/")
    country = segments[2]
    area_one = None
    area_two = None
    locality = None
    if len(segments) > 3:
      area_one = segments[3]
    if len(segments) > 4:
      area_two = segments[4]
    if len(segments) > 5:
      locality = segments[5]
    result = {
      'id': loc.id,
      'text': loc.name,
      'url': url,
      'type': 'location',
      'subtext': loc.country.name,
      'data': {
        'country': country,
        'area_one': area_one,
        'area_two': area_two,
        'locality': locality
      }
    }
    results.append(result)
  results.reverse()
  return { 'data': results }

@bp.route("/typeahead/nearby")
@cache.cached(query_string=True)
def get_typeahead_nearby():
  latitude = request.args.get('latitude')
  longitude = request.args.get('longitude')
  if not latitude:
    return { 'data': [] }
  limit = request.args.get('limit')
  results = get_nearby_spots(latitude, longitude, limit, None)
  return {
    'data': list(map(typeahead_from_spot, results))
  }
