import os
from flask import Blueprint, request
from app.models import User, DivePartnerAd
from sqlalchemy import or_, sql
from sqlalchemy.orm import joinedload
from app import db
from flask_jwt_extended import jwt_required, get_current_user
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

bp = Blueprint('buddy', __name__, url_prefix="/buddy")

@bp.route('/add', methods=["POST"])
def add_buddy():
  user_id = request.json.get('user_id')
  area_one_id = request.json.get('area_one_id')
  area_two_id = request.json.get('area_two_id')
  country_id = request.json.get('country_id')
  locality_id = request.json.get('locality_id')
  latitude = request.json.get('latitude')
  longitude = request.json.get('longitude')

  buddy = DivePartnerAd(
    user_id=user_id,
    area_one_id=area_one_id, 
    area_two_id=area_two_id,
    country_id=country_id,
    locality_id=locality_id,
    latitude=latitude,
    longitude=longitude,
  )
  db.session.add(buddy)
  db.session.commit()
  buddy.id
  return { 'data': buddy.get_dict() }

@bp.route('/get')
def get_buddies():
  area_one_id = request.args.get('area_one')
  area_two_id = request.args.get('area_two')
  country_id = request.args.get('country')
  locality_id = request.args.get('locality')

  if not area_one_id and not area_two_id and not country_id and not locality_id:
    dive_partners = User.query.join(DivePartnerAd).filter(User.id==DivePartnerAd.user_id).limit(10).all()
    partners = []
    for partner in dive_partners:
      partner_dict = partner.get_dict()
      partners.append(partner_dict)
    return { 'data': partners }

  dive_partners = DivePartnerAd.query \
    .options(joinedload('user')) \
    .filter(
      or_(
        DivePartnerAd.area_one_id==area_one_id if area_one_id else sql.false(),
        DivePartnerAd.area_two_id==area_two_id if area_two_id else sql.false(),
        DivePartnerAd.locality_id==locality_id if locality_id else sql.false(),
        DivePartnerAd.country_id==country_id if country_id else sql.false(),
    )).all()
  partners = []
  for partner in dive_partners:
    partner_dict = partner.user.get_dict()
    partners.append(partner_dict)
  return { 'data': partners }

@bp.route('/connect', methods=['POST'])
@jwt_required()
def connect_buddy():
  current_user = get_current_user()
  user_id = request.json.get('userId')
  user = User.query.filter_by(id=user_id).first()

  message = Mail(
      from_email=('hello@zentacle.com', 'Zentacle'),
      to_emails=user.email)

  message.template_id = 'd-bd201d4de3ad404ebf5b8fe7045c15a3'
  message.reply_to = current_user.email
  message.dynamic_template_data = {
      'receiver_name': user.first_name,
      'request_name': current_user.display_name,
      'request_username': current_user.username,
      'request_email': current_user.email,
  }
  try:
      sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
      sg.send(message)
  except Exception as e:
      print(e.body)
  return {
    'msg': 'We\'ve sent them an email with your contact info!',
  }