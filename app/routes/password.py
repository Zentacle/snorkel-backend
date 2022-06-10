import os
import secrets
from flask import Blueprint, request
from app.models import User, PasswordReset
from app import db
from flask_jwt_extended import (
  create_access_token,
  create_refresh_token,
  set_access_cookies,
  set_refresh_cookies,
)
from datetime import datetime
import bcrypt
from sqlalchemy import func
from flask.helpers import make_response
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

bp = Blueprint('password', __name__, url_prefix="/password")

@bp.route('/password/request', methods=['POST'])
def request_reset_password():
  email = request.json.get('email')
  user = User.query.filter(func.lower(User.email)==email.lower()).first_or_404()

  reset_obj = PasswordReset(
    user_id=user.id,
    token=secrets.token_urlsafe(),
  )
  db.session.add(reset_obj)
  db.session.commit()

  message = Mail(
      from_email=('hello@zentacle.com', 'Zentacle'),
      to_emails=email)

  message.template_id = 'd-61fcfe0f648c4237849621389db5c75c'
  message.reply_to = 'mayank@zentacle.com'
  message.dynamic_template_data = {
      'url': 'https://www.zentacle.com/resetpassword?token='+reset_obj.token,
  }
  try:
      sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
      sg.send(message)
  except Exception as e:
      print(e.body)

  return {'msg': 'Password reset sent, check your email for a reset link'}

@bp.route('/password/reset', methods=['POST'])
def reset_password():
  token = request.json.get('token')
  password = request.json.get('password')

  reset_obj = PasswordReset.query.filter_by(token=token).first()
  if reset_obj:
    if reset_obj.token_expiry < datetime.utcnow():
      return {'msg': 'Link expired. Try reseting your password again'}, 401
    user_id = reset_obj.user_id
    user = User.query.filter_by(id=user_id).first()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user.password = hashed_password
    db.session.commit()
    refresh_token = create_refresh_token(identity=user.id)
    auth_token = create_access_token(identity=user.id)
    responseObject = {
      'status': 'success',
      'msg': 'Successfully reset password. You are now logged in',
      'auth_token': auth_token,
      'refresh_token': refresh_token
    }
    resp = make_response(responseObject)
    set_access_cookies(resp, auth_token)
    set_refresh_cookies(resp, refresh_token)
    db.session.delete(reset_obj)
    db.session.commit()
    return resp
  return {'msg': 'No token or password provided'}, 422