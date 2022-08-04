from flask import Blueprint, request
from app.helpers.merge_area_one import merge_area_one
from app.models import (
  Country,
  AreaOne,
  AreaTwo,
  Locality,
  Spot
)
from app import db, cache
from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload

bp = Blueprint('locality', __name__, url_prefix="/locality")

@bp.route("/locality")
@cache.cached(query_string=True)
def locality_get():
  limit = request.args.get('limit') if request.args.get('limit') else 15
  country_short_name = request.args.get('country')
  area_one_short_name = request.args.get('area_one')
  area_two_short_name = request.args.get('area_two')
  localities = Locality.query
  if country_short_name:
    localities = localities.filter(Locality.country.has(short_name=country_short_name))
  if area_one_short_name:
    localities = localities.filter(Locality.area_one.has(short_name=area_one_short_name))
  if area_two_short_name:
    localities = localities.filter(Locality.area_two.has(short_name=area_two_short_name))
  localities = localities \
    .options(joinedload('area_two')) \
    .options(joinedload('area_one')) \
    .options(joinedload('country'))
  if limit != 'none':
    localities = localities.limit(limit)
  localities = localities.all()
  data = []
  for locality in localities:
    locality_data = locality.get_dict()
    if locality_data.get('area_two'):
      locality_data['area_two'] = locality_data.get('area_two').get_simple_dict()
    if locality_data.get('area_one'):
      locality_data['area_one'] = locality_data.get('area_one').get_simple_dict()
    if locality_data.get('country'):
      locality_data['country'] = locality_data.get('country').get_simple_dict()
    data.append(locality_data)
  #   if 'url' in locality_data and not locality.url:
  #     locality.url = locality_data['url']
  # db.session.commit()
  return { 'data': data }

@bp.route("/area_two")
@cache.cached(query_string=True)
def get_area_two():
  limit = request.args.get('limit') if request.args.get('limit') else 25
  country_short_name = request.args.get('country')
  area_one_short_name = request.args.get('area_one')
  localities = AreaTwo.query
  if country_short_name:
    localities = localities.filter(AreaTwo.country.has(short_name=country_short_name))
  if area_one_short_name:
    localities = localities.filter(AreaTwo.area_one.has(short_name=area_one_short_name))
  localities = localities \
    .options(joinedload('area_one')) \
    .options(joinedload('country'))
  if limit != 'none':
    localities = localities.limit(limit)
  localities = localities.all()
  data = []
  for locality in localities:
    locality_data = locality.get_dict()
    if locality.area_one:
      locality_data['area_one'] = locality.area_one.get_simple_dict()
    if locality.country:
      locality_data['country'] = locality.country.get_simple_dict()
    data.append(locality_data)
  return { 'data': data }

@bp.route("/area_one")
@cache.cached(query_string=True)
def get_area_one():
  country_short_name = request.args.get('country')
  country = Country.query.filter_by(short_name=country_short_name).first()
  localities = AreaOne.query
  if country:
    localities = localities.filter_by(country_id=country.id)
  localities = localities.options(joinedload('country')) \
    .all()
  data = []
  for locality in localities:
    locality_data = locality.get_dict()
    if locality_data.get('country'):
      locality_data['country'] = locality_data.get('country').get_simple_dict()
    data.append(locality_data)
  return { 'data': data }

@bp.route("/country")
@cache.cached()
def get_country():
  sq = db.session.query(Spot.country_id, func.count(Spot.id).label('count')).group_by(Spot.country_id).subquery()
  localities = db.session.query(Country, sq.c.count).join(sq, sq.c.country_id == Country.id).all()
  data = []
  for (locality, count) in localities:
    dict = locality.get_dict()
    dict['num_spots'] = count
    data.append(dict)
  data.sort(reverse=True, key=lambda country:country['num_spots'])
  return { 'data': data }

@bp.route("/<country>/<area_one>")
def get_wildcard_locality(country, area_one):
  locality = AreaOne.query \
    .filter(
      and_(
        AreaOne.short_name==area_one,
        AreaOne.country.has(short_name=country)
      )
    ).first_or_404()
  data = []
  for spot in locality.spots:
    data.append(spot.get_dict())
  return { 'data': data }

@bp.route("/merge/a2/<stable_id>/<remove_id>")
def merge_a2(stable_id, remove_id):
  stable = AreaOne.query.filter_by(id=stable_id).first_or_404()
  remove = AreaOne.query.filter_by(id=remove_id).first_or_404()
  if stable.short_name != remove.short_name or stable.country_id != remove.country_id:
    return { 'status': 'objects didnt match' }
  results = merge_area_one(stable_id, remove_id)
  country = Country.query.filter_by(id=stable.country_id).first_or_404()
  country_short_name = country.short_name
  area_1_short_name = stable.short_name
  stable.url = f'/loc/{country_short_name}/{area_1_short_name}',
  return { 'status': results }
