from flask import Blueprint, request
from app.models import (
  Country,
  AreaOne,
  AreaTwo,
  Locality,
)
from app import db

bp = Blueprint('loc', __name__, url_prefix="/loc")

@bp.route("/country/patch", methods=["PATCH"])
def patch_country():
  id = request.json.get('id')
  loc = Country.query.filter_by(id=id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(loc, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  loc.id
  return loc.get_dict(), 200

@bp.route("/area_one/patch", methods=["PATCH"])
def patch_loc_one():
  id = request.json.get('id')
  loc = AreaOne.query.filter_by(id=id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(loc, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  loc.id
  return loc.get_dict(), 200

@bp.route("/area_two/patch", methods=["PATCH"])
def patch_loc_two():
  id = request.json.get('id')
  loc = AreaTwo.query.filter_by(id=id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(loc, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  loc.id
  return loc.get_dict(), 200

@bp.route("/locality/patch", methods=["PATCH"])
def patch_locality():
  id = request.json.get('id')
  loc = Locality.query.filter_by(id=id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  try:
    for key in updates.keys():
      setattr(loc, key, updates.get(key))
  except ValueError as e:
    return e, 500
  db.session.commit()
  loc.id
  return loc.get_dict(), 200
