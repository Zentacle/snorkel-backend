from flask import Blueprint, request
from app.models import DiveShop
from app import db
from flask_jwt_extended import jwt_required, get_current_user

bp = Blueprint('dive_shop', __name__, url_prefix="/shop")

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

  return { 'data': dive_shop.get_dict() }

@bp.route('/patch/<int:id>', methods=['PATCH'])
@jwt_required()
def update_dive_shop(id):
  dive_shop = dive_shop = DiveShop.query.get(id)
  user = get_current_user()
  
  if dive_shop:
    # restrict access to patching a dive log
    if dive_shop.owner_user_id != id or not user.admin:
      return "Only shop owner and admin can perform this action", 403

    updates = request.json
    try:
      for key in updates.keys():
        setattr(dive_shop, key, updates.get(key))
    except ValueError as e:
      return e, 500
    db.session.commit()
    data = dive_shop.get_dict()

    return { 'data': data }
  
  return 'No dive shop found', 400 
