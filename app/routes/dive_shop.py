from flask import Blueprint, request
from app.models import DiveShop
from app import db
from flask_jwt_extended import jwt_required

bp = Blueprint('dive_shop', __name__, url_prefix="/dive_shops")

@bp.route('/get', methods=['GET'])
def fetch_dive_shops():
  dive_shops = DiveShop.query.all()
  data = [dive_shop.get_simple_dict() for dive_shop in dive_shops]
  return { 'data': data }

@bp.route('/get/<int:id>', methods=['GET'])
def fetch_dive_shop(id):
  dive_shop = DiveShop.query.get(id)
  if dive_shop:
    data = dive_shop.get_dict()
    return { 'data': data }
  return 'No dive shop found', 400

@bp.route('/create', methods=['POST'])
@jwt_required()
def create_dive_shop():
  url = request.json.get('url')
  fareharbor_url = request.json.get('fareharbor_url')
  address1 = request.json.get('address1')
  address2 = request.json.get('address2')
  city = request.json.get('city')
  state = request.json.get('state')
  zip = request.json.get('zip')
  logo_img = request.json.get('logo_img')
  latitude = request.json.get('latitude')
  longitude = request.json.get('longitude')
  locality_id = request.json.get('locality_id')
  area_one_id = request.json.get('area_one_id')
  area_two_id  = request.json.get('area_two_id')
  country_id = request.json.get('country_id')

  dive_shop = DiveShop(
    url=url,
    fareharbor_url=fareharbor_url,
    address1=address1,
    address2=address2,
    city=city,
    state=state,
    zip=zip,
    logo_img=logo_img,
    latitude=latitude,
    longitude=longitude,
    locality_id=locality_id,
    area_one_id=area_one_id,
    area_two_id=area_two_id,
    country_id=country_id
  )

  db.session.add(dive_shop)
  db.session.commit()

  return { 'dive_shop': dive_shop.get_dict() }
