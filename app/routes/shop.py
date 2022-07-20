import requests
import os
from app.helpers.wally_integration import mint_nft
import boto3
import io
from flask import Blueprint, request
from sqlalchemy import and_, not_, or_
from app.models import DiveShop, Review, Spot
from app import db, cache
from flask_jwt_extended import jwt_required, get_current_user

bp = Blueprint('shop', __name__, url_prefix="/shop")
wally_api_base = os.environ.get('WALLY_API')
wally_auth_token = os.environ.get('WALLY_AUTH_TOKEN')

@bp.route('/get', methods=['GET'])
def fetch_dive_shops():
  dive_shops = DiveShop.query.all()
  data = [dive_shop.get_simple_dict() for dive_shop in dive_shops]
  return { 'data': data }

@bp.route('/get/<int:id>', methods=['GET'])
def fetch_dive_shop(id):
  dive_shop = DiveShop.query.get_or_404(id)
  data = dive_shop.get_dict()
  return { 'data': data }

@bp.route('/create', methods=['POST'])
@jwt_required()
def create_dive_shop():
  user = get_current_user()
  if not user.admin:
    return {'msg': 'You must be an admin to that'}, 403

  padi_store_id = request.json.get('padi_store_id')
  url = request.json.get('url')
  name=request.json.get('name')
  fareharbor_url = request.json.get('fareharbor_url')
  address1 = request.json.get('address1')
  address2 = request.json.get('address2')
  country_name = request.json.get('country_name')
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
    name=name,
    padi_store_id=padi_store_id,
    fareharbor_url=fareharbor_url,
    address1=address1,
    address2=address2,
    country_name=country_name,
    city=city,
    state=state,
    zip=zip,
    logo_img=logo_img,
    latitude=latitude,
    longitude=longitude,
    locality_id=locality_id,
    area_one_id=area_one_id,
    area_two_id=area_two_id,
    country_id=country_id,
  )
  db.session.add(dive_shop)
  db.session.commit()

  request_url = f'{wally_api_base}/wallets/create'
  headers = {
    'Authorization': f'Bearer {wally_auth_token}',
    'Content-Type': 'application/json',
  }

  payload = {
    'id': 'shop_' + str(dive_shop.id),
    'email': user.email, # owner is the current user, so owner email is current user email
    'tags': ['shop']
  }

  response = requests.post(request_url, headers=headers, json=payload)
  response.raise_for_status()

  return { 'data': dive_shop.get_dict() }

@bp.route('/patch/<int:id>', methods=['PATCH'])
@jwt_required()
def update_dive_shop(id):
  dive_shop = DiveShop.query.get_or_404(id)
  user = get_current_user()

  # restrict access to patching a dive log
  if dive_shop.owner_user_id != user.id and not user.admin:
    return { "msg": "Only shop owner and admin can perform this action" }, 403

  updates = request.json
  try:
    for key in updates.keys():
      setattr(dive_shop, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  data = dive_shop.get_dict()

  return { 'data': data }

@bp.route('/<int:id>/stamp_image', methods=['POST'])
@jwt_required()
def upload_stamp_image(id):
  if 'file' not in request.files:
    return { 'msg': 'No file included in request' }, 422
  request_url = f'{wally_api_base}/files/upload'
  headers = {
    'Authorization': f'Bearer {wally_auth_token}'
  }

  response = requests.post(request_url, headers=headers, data={}, files=request.files)
  response.raise_for_status()
  data = response.json()

  dive_shop = DiveShop.query.get_or_404(id)
  setattr(dive_shop, 'stamp_uri', data.get('uri'))
  db.session.commit()

  return { 'msg': 'dive shop successfully updated' }

@bp.route('/<int:id>/logo', methods=['POST'])
@jwt_required()
def upload(id):
  if 'file' not in request.files:
    return { 'msg': 'No file included in request' }, 422
  # If the user does not select a file, the browser submits an
  # empty file without a filename.
  file = request.files.get('file')
  if file.filename == '':
      return { 'msg': 'Submitted an empty file' }, 422
  import uuid
  s3_key = str(get_current_user().id) + '_' + str(uuid.uuid4())
  contents = file.read()
  bucket = os.environ.get('S3_BUCKET_NAME')
  s3_url = boto3.client("s3").upload_fileobj(io.BytesIO(contents), bucket, 'shops/'+s3_key,
                            ExtraArgs={'ACL': 'public-read',
                                        'ContentType': file.content_type}
                            )
  s3_url = f'https://{bucket}.s3.amazonaws.com/shops/{s3_key}'

  dive_shop = DiveShop.query.get_or_404(id)
  setattr(dive_shop, 'logo_img', s3_url)
  db.session.commit()

  return { 'msg': 'dive shop successfully updated' }

@bp.route('/typeahead')
@cache.cached(query_string=True)
def get_typeahead():
  query = request.args.get('query')
  results = []
  dive_shops = DiveShop.query \
    .filter(
      or_(
        DiveShop.name.ilike('%'+query+'%'),
        DiveShop.city.ilike('%'+query+'%'),
        DiveShop.state.ilike('%'+query+'%')
      )
    ) \
    .limit(25) \
    .all()

  for shop in dive_shops:
    result = {
      'id': shop.id,
      "text": shop.name,
      'subtext': f'{shop.city}, {shop.state}'
    }
    results.append(result)

  return { "data": results }

@bp.route('/<int:id>/mint_dive_stamp', methods=["POST"])
@jwt_required()
def mint_dive_stamp(id):
  user = get_current_user()
  # restrict access
  dive_shop = DiveShop.query.get_or_404(id).get_dict()
  if dive_shop.get('owner_user_id') != user.id and not user.admin:
    return { "msg": "Only shop owner and admin can perform this action" }, 403

  current_review = Review.query.get_or_404(request.json.get('review_id')).get_dict()
  beach_id = current_review.get('beach_id')
  beach = Spot.query.get_or_404(beach_id).get_dict()
  if (dive_shop.get('stamp_uri')):
    data = mint_nft(current_review=current_review, dive_shop=dive_shop, beach=beach, user=user)

    return {
      'data': data
    }
 
  return {
    'msg': 'This dive shop needs a stamp image uri to be able to mint an nft'
  }
