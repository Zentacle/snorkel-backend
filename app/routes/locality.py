from flask import Blueprint, request
from app.helpers.merge_area_one import merge_area_one
from app.helpers.get_limit import get_limit
from app.models import (
    Country,
    AreaOne,
    AreaTwo,
    Locality,
    Spot,
    DiveShop
)
from app import db, cache
from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload

bp = Blueprint('locality', __name__, url_prefix="/locality")


@bp.route("/locality")
@cache.cached(query_string=True)
def get_locality():
    limit = get_limit(request.args.get('limit'), 15)
    table = Spot
    if request.args.get('shops'):
        table = DiveShop
    country_short_name = request.args.get('country')
    area_one_short_name = request.args.get('area_one')
    area_two_short_name = request.args.get('area_two')
    sq = db.session \
        .query(
            table.country_id,
            table.area_one_id,
            table.area_two_id,
            table.locality_id,
            func.count(table.id).label('count')
        ).group_by(table.area_one_id, table.country_id, table.area_two_id, table.locality_id).subquery()
    localities = db.session.query(
        Locality,
        sq.c.count,
    ).join(sq, and_(
        sq.c.country_id == Locality.country_id,
        sq.c.area_one_id == Locality.area_one_id,
        sq.c.area_two_id == Locality.area_two_id,
        sq.c.locality_id == Locality.id,
    )).order_by(db.desc('count'))
    if country_short_name:
        localities = localities.filter(
            Locality.country.has(short_name=country_short_name))
    if area_one_short_name:
        localities = localities.filter(
            Locality.area_one.has(short_name=area_one_short_name))
    if area_two_short_name:
        localities = localities.filter(
            Locality.area_two.has(short_name=area_two_short_name))
    localities = localities.options(joinedload('country')) \
        .options(joinedload('area_one')) \
        .options(joinedload('area_two')) \
        .limit(limit) \
        .all()
    data = []
    for (locality, count) in localities:
        locality_data = locality.get_dict()
        if locality_data.get('country'):
            locality_data['country'] = locality_data.get(
                'country').get_simple_dict()
        if locality_data.get('area_one'):
            locality_data['area_one'] = locality_data.get(
                'area_one').get_simple_dict()
        if locality_data.get('area_two'):
            locality_data['area_two'] = locality_data.get(
                'area_two').get_simple_dict()
        locality_data['num_spots'] = count
        data.append(locality_data)
    return {'data': data}


@bp.route("/area_two")
@cache.cached(query_string=True)
def get_area_two():
    limit = get_limit(request.args.get('limit'), 15)
    table = Spot
    if request.args.get('shops'):
        table = DiveShop
    country_short_name = request.args.get('country')
    area_one_short_name = request.args.get('area_one')
    sq = db.session \
        .query(
            table.country_id,
            table.area_one_id,
            table.area_two_id,
            func.count(table.id).label('count')
        ).group_by(table.area_one_id, table.country_id, table.area_two_id).subquery()
    localities = db.session.query(
        AreaTwo,
        sq.c.count,
    ).join(sq, and_(sq.c.area_one_id == AreaTwo.area_one_id, sq.c.country_id == AreaTwo.country_id, sq.c.area_two_id == AreaTwo.id)).order_by(db.desc('count'))
    if country_short_name:
        localities = localities.filter(
            AreaTwo.country.has(short_name=country_short_name))
    if area_one_short_name:
        localities = localities.filter(
            AreaTwo.area_one.has(short_name=area_one_short_name))
    localities = localities.options(joinedload('country')) \
        .options(joinedload('area_one')) \
        .limit(limit) \
        .all()
    data = []
    for (locality, count) in localities:
        locality_data = locality.get_dict()
        if locality_data.get('country'):
            locality_data['country'] = locality_data.get(
                'country').get_simple_dict()
        if locality_data.get('area_one'):
            locality_data['area_one'] = locality_data.get(
                'area_one').get_simple_dict()
        locality_data['num_spots'] = count
        data.append(locality_data)
    return {'data': data}


@bp.route("/area_one")
@cache.cached(query_string=True)
def get_area_one():
    limit = get_limit(request.args.get('limit'), 15)
    table = Spot
    if request.args.get('shops'):
        table = DiveShop
    country_short_name = request.args.get('country')
    sq = db.session \
        .query(
            table.country_id,
            table.area_one_id,
            func.count(table.id).label('count')
        ).group_by(table.area_one_id, table.country_id).subquery()
    localities = db.session.query(
        AreaOne,
        sq.c.count,
    ).join(sq, and_(sq.c.area_one_id == AreaOne.id, sq.c.country_id == AreaOne.country_id)).order_by(db.desc('count'))
    if country_short_name:
        localities = localities.filter(
            AreaOne.country.has(short_name=country_short_name))
    localities = localities.options(joinedload('country')) \
        .limit(limit) \
        .all()
    data = []
    for (locality, count) in localities:
        locality_data = locality.get_dict()
        if locality_data.get('country'):
            locality_data['country'] = locality_data.get(
                'country').get_simple_dict()
        locality_data['num_spots'] = count
        data.append(locality_data)
    return {'data': data}


@bp.route("/country")
@cache.cached()
def get_country():
    limit = get_limit(request.args.get('limit'), 15)
    table = Spot
    if request.args.get('shops'):
        table = DiveShop
    sq = db.session \
        .query(
            table.country_id,
            func.count(table.id).label('count')
        ).group_by(table.country_id).subquery()
    localities = db.session.query(Country, sq.c.count) \
        .join(sq, sq.c.country_id == Country.id).order_by(db.desc('count')) \
        .limit(limit) \
        .all()
    data = []
    for (locality, count) in localities:
        dict = locality.get_dict()
        dict['num_spots'] = count
        data.append(dict)
    return {'data': data}


@bp.route("/<country>/<area_one>")
def get_wildcard_locality(country, area_one):
    locality = AreaOne.query \
        .filter(
            and_(
                AreaOne.short_name == area_one,
                AreaOne.country.has(short_name=country)
            )
        ).first_or_404()
    data = []
    for spot in locality.spots:
        data.append(spot.get_dict())
    return {'data': data}


@bp.route("/merge/a2/<stable_id>/<remove_id>")
def merge_a2(stable_id, remove_id):
    stable = AreaOne.query.filter_by(id=stable_id).first_or_404()
    remove = AreaOne.query.filter_by(id=remove_id).first_or_404()
    if stable.short_name != remove.short_name or stable.country_id != remove.country_id:
        return {'status': 'objects didnt match'}
    results = merge_area_one(stable_id, remove_id)
    country = Country.query.filter_by(id=stable.country_id).first_or_404()
    country_short_name = country.short_name
    area_1_short_name = stable.short_name
    stable.url = f'/loc/{country_short_name}/{area_1_short_name}'
    db.session.commit()
    return {'status': results}


@bp.route("/generate_urls")
def gen_urls():
    area_ones = AreaOne.query.options(joinedload('country')).all()
    results = []
    for area_one in area_ones:
        result = area_one.get_dict()
        result['url'] = area_one.get_url(area_one.country)
        results.append(result)
        area_one.url = area_one.get_url(area_one.country)
    db.session.commit()
    return {'data': results}
