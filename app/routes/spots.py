import os
from flask import Blueprint, request, abort
from app.models import (
   Review,
   Spot,
   ShoreDivingData,
   Locality,
   AreaTwo,
   AreaOne,
   Country,
   WannaDiveData,
   Tag,
   Image,
   tags
)
from app import db, cache, get_summary_reviews_helper
import requests
from flask_jwt_extended import (
  jwt_required,
  get_current_user,
  get_jwt_identity,
)
from sqlalchemy import or_, and_, sql
from sqlalchemy.orm import joinedload
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.helpers.get_localities import get_localities
from app.helpers.get_nearby_spots import get_nearby_spots
import newrelic.agent

bp = Blueprint('spots', __name__, url_prefix="/spots")

@bp.route("/get")
@cache.cached(query_string=True)
def get_spots():
  """ Get Dive Sites/Beaches
  ---
  get:
      summary: Get dive sites
      description: Get dive sites
      parameters:
          - name: beach_id
            in: body
            description: Beach ID
            type: string
            required: false
          - name: locality
            in: body
            description: locality (eg. Kihei)
            type: string
            required: false
          - name: area_two
            in: body
            description: area_two (eg. Maui)
            type: string
            required: false
          - name: area_one
            in: body
            description: area_one (eg. Hawaii)
            type: string
            required: false
          - name: country
            in: body
            description: country (eg. USA)
            type: string
            required: false
          - name: sort
            in: body
            description: sort (latest, most_reviewed, top). defaults to top
            type: string
            required: false
          - name: limit
            in: body
            description: limit on number of results returned (default 15)
            type: string
            required: false
      responses:
          200:
              description: Returns singular beach object or list of beach objects
              content:
                application/json:
                  schema: BeachSchema
          400:
              content:
                application/json:
                  schema:
                    Error:
                      properties:
                        msg:
                          type: string
              description: Wrong password.
  """
  newrelic.agent.capture_request_params()
  is_shorediving = False
  area = None
  spot = None
  sd_spot = None
  if request.args.get('beach_id') or request.args.get('region') or request.args.get('sd_id'):
    if request.args.get('beach_id'):
      beach_id = request.args.get('beach_id')
      spot = Spot.query \
        .options(joinedload('locality')) \
        .options(joinedload('area_two')) \
        .options(joinedload('area_one')) \
        .options(joinedload('country')) \
        .options(joinedload('shorediving_data')) \
        .filter_by(id=beach_id) \
        .first_or_404()
      if spot.shorediving_data:
        sd_spot = spot.shorediving_data
    elif request.args.get('region'):
      is_shorediving = True
      region = request.args.get('region')
      destination = request.args.get('destination')
      site = request.args.get('site')
      sd_spot = ShoreDivingData.query \
        .options(joinedload('spot')) \
        .filter(and_(
          ShoreDivingData.region_url==region,
          ShoreDivingData.destination_url==destination,
          ShoreDivingData.name_url==site,
        )) \
        .first_or_404()
      spot = Spot.query \
        .options(joinedload('locality')) \
        .options(joinedload('area_two')) \
        .options(joinedload('area_one')) \
        .options(joinedload('country')) \
        .filter_by(id=sd_spot.spot_id) \
        .first()
    elif request.args.get('sd_id'):
      is_shorediving = True
      fsite = request.args.get('sd_id')
      sd_spot = ShoreDivingData.query \
        .options(joinedload('spot')) \
        .filter_by(id=fsite) \
        .first_or_404()
      spot = Spot.query \
        .options(joinedload('locality')) \
        .options(joinedload('area_two')) \
        .options(joinedload('area_one')) \
        .options(joinedload('country')) \
        .filter_by(id=sd_spot.spot_id) \
        .first()
    spot_data = spot.get_dict()
    if is_shorediving and sd_spot:
      spot_data['sd_url'] = sd_spot.get_url()
      spot_data['country'] = sd_spot.get_region_dict()
      spot_data['area_one'] = sd_spot.get_destination_dict()
      spot_data['area_two'] = None
      spot_data['locality'] = None
    else:
      if spot_data['locality']:
        spot_data['locality'] = spot.locality.get_dict(spot.country, spot.area_one, spot.area_two)
      if spot_data['area_two']:
        spot_data['area_two'] = spot.area_two.get_dict(spot.country, spot.area_one)
      if spot_data['area_one']:
        spot_data['area_one'] = spot.area_one.get_dict(spot.country)
      if spot_data['country']:
        spot_data['country'] = spot.country.get_dict()
    beach_id = spot.id
    if not spot.location_google and spot.latitude and spot.longitude:
      spot_data['location_google'] = ('http://maps.google.com/maps?q=%(latitude)f,%(longitude)f'
        % { 'latitude': spot.latitude, 'longitude': spot.longitude}
      )
    spot_data["ratings"] = get_summary_reviews_helper(beach_id)
    return { 'data': spot_data }
  query = Spot.query
  if request.args.get('unverified'):
    query = query.filter(Spot.is_verified.isnot(True))
  else:
    query = query.filter(Spot.is_verified.isnot(False))
    query = query.filter(Spot.is_deleted.isnot(True))
  locality_name = request.args.get('locality')
  area_two_name = request.args.get('area_two')
  area_one_name = request.args.get('area_one')
  country_name = request.args.get('country')
  if locality_name:
    area_two_spot_query = Spot.area_two.has(short_name=area_two_name)
    area_two_area_query = Locality.area_two.has(short_name=area_two_name)
    if area_two_name == '_':
      area_two_spot_query = sql.true()
      area_two_area_query = sql.true()
    query = query.filter(
      and_(
        Spot.locality.has(short_name=locality_name),
        area_two_spot_query,
        Spot.area_one.has(short_name=area_one_name),
        Spot.country.has(short_name=country_name),
      )
    )
    area = Locality.query \
      .options(joinedload('area_two')) \
      .options(joinedload('area_one')) \
      .options(joinedload('country')) \
      .filter(
        Locality.short_name==locality_name,
        area_two_area_query,
        Locality.area_one.has(short_name=area_one_name),
        Locality.country.has(short_name=country_name),
      ) \
      .first_or_404()
  elif area_two_name:
    query = query.filter(
      and_(
        Spot.area_two.has(short_name=area_two_name),
        Spot.area_one.has(short_name=area_one_name),
        Spot.country.has(short_name=country_name),
      )
    )
    area = AreaTwo.query \
      .options(joinedload('area_one')) \
      .options(joinedload('country')) \
      .filter(
        and_(
          AreaTwo.short_name==area_two_name,
          AreaTwo.area_one.has(short_name=area_one_name),
          AreaTwo.country.has(short_name=country_name),
        )
      ) \
      .first_or_404()
  elif area_one_name:
      query = query.filter(
        and_(
          Spot.area_one.has(short_name=area_one_name),
          Spot.country.has(short_name=country_name),
        )
      )
      area = AreaOne.query \
        .options(joinedload('country')) \
        .filter(
          and_(
            AreaOne.short_name==area_one_name,
            AreaOne.country.has(short_name=country_name),
          )
        ) \
        .first_or_404()
  elif country_name:
      query = query.filter(Spot.country.has(short_name=country_name))
      area = Country.query \
        .filter_by(short_name=country_name) \
        .first_or_404()
  difficulty_filter = request.args.get('difficulty')
  if difficulty_filter:
    query = query.filter(Spot.difficulty==difficulty_filter)
  access_filter = request.args.get('entry')
  if access_filter:
    query = query.filter(Spot.tags.any(short_name=access_filter))
  sort_param = request.args.get('sort')
  if sort_param == 'latest':
    query = query.order_by(Spot.last_review_date.desc().nullslast())
  elif sort_param == 'most_reviewed':
    query = query.order_by(Spot.num_reviews.desc().nullslast(), Spot.rating.desc())
  elif sort_param == 'top':
    query = query.order_by(Spot.rating.desc().nullslast(), Spot.num_reviews.desc())
  else:
    query = query.order_by(Spot.num_reviews.desc().nullslast())
  if request.args.get('limit') != 'none':
    limit = request.args.get('limit') if request.args.get('limit') else 15
    query = query.limit(limit)
  query = query.options(joinedload(Spot.shorediving_data))
  spots = query.all()
  if sort_param == 'top':
    spots.sort(reverse=True, key=lambda spot: spot.get_confidence_score())
  output = []
  for spot in spots:
    spot_data = spot.get_dict()
    if request.args.get('ssg'):
      spot_data['beach_name_for_url'] = spot.get_beach_name_for_url()
    if spot.shorediving_data:
      spot_data['sd_url'] = spot.shorediving_data.get_url()
    if not spot.location_google and spot.latitude and spot.longitude:
      spot_data['location_google'] = ('http://maps.google.com/maps?q=%(latitude)f,%(longitude)f'
        % { 'latitude': spot.latitude, 'longitude': spot.longitude}
      )
    output.append(spot_data)
  resp = { 'data': output }
  if area:
    area_data = area.get_dict()
    if area_data.get('area_two'):
      area_data['area_two'] = area_data.get('area_two').get_dict(area.country, area.area_one)
    if area_data.get('area_one'):
      area_data['area_one'] = area_data.get('area_one').get_dict(area.country)
    if area_data.get('country'):
      area_data['country'] = area_data.get('country').get_dict()
    resp['area'] = area_data
  return resp

@bp.route("/search")
def search_spots():
  """ Search Spots
  ---
  get:
      summary: Search
      description: search
      parameters:
          - name: query
            in: query
            description: search term
            type: string
            required: true
          - name: activity
            in: query
            description: activity filter. either "scuba", "freediving", or "snorkel"
            type: string
            required: false
          - name: difficulty
            in: query
            description: difficulty filter. either "beginner", "intermediate", or "advanced"
            type: string
            required: false
          - name: entry
            in: query
            description: entry filter. either "shore" or "boat"
            type: string
            required: false
          - name: max_depth
            in: query
            description: max_depth filter
            type: int
            required: false
          - name: max_depth_type
            in: query
            description: max_depth filter units. either "m" or "ft"
            type: string
            required: false
          - name: sort
            in: query
            description: sort either "rating" or "popularity"
            type: string
            required: false
          - name: limit
            in: query
            description: the max number of results in the response (default 50)
            type: int
            required: false
          - name: offset
            in: query
            description: offset in order to paginate the results
            type: int
            required: false
      responses:
          200:
              description: Returns singular beach object or list of beach objects
              content:
                application/json:
                  schema: BeachSchema
  """
  search_term = request.args.get('query')
  limit = request.args.get('limit') \
    if request.args.get('limit') \
    else 50
  offset = int(request.args.get('offset')) if request.args.get('offset') else 0
  if not search_term:
    search_term = request.args.get('search_term')
  difficulty = request.args.get('difficulty')
  activity = request.args.get('activity')
  entry = request.args.get('entry')
  sort = request.args.get('sort')
  difficulty_query = sql.true()
  entry_query = sql.true()
  activity_query = sql.true()
  sort_query = sql.true()
  if difficulty:
    difficulty_query = Spot.difficulty.__eq__(difficulty)
  if entry:
    entry_query = Spot.tags.any(short_name=entry)
  # if activity:
    # activity_query = Spot.
  spots = Spot.query.filter(
    and_(
      or_(
        Spot.name.ilike('%' + search_term + '%'),
        Spot.location_city.ilike('%'+ search_term + '%'),
        Spot.description.ilike('%'+ search_term + '%')
      ),
      Spot.is_verified.isnot(False),
      Spot.is_deleted.isnot(True)),
      difficulty_query,
      entry_query,
    ) \
    .offset(offset) \
    .limit(limit) \
    .all()
  output = []
  for spot in spots:
    spot_data = spot.get_dict()
    output.append(spot_data)
  return { 'data': output }

@bp.route("/add/script", methods=["POST"])
def add_spot_script():
  name = request.json.get('name')
  description = request.json.get('description')
  directions = request.json.get('directions')
  id = request.json.get('id')
  name_url = request.json.get('name_url')
  destination = request.json.get('destination')
  destination_url = request.json.get('destination_url')
  region = request.json.get('region')
  region_url = request.json.get('region_url')
  location_city = destination + ', ' + region
  area_two_id = request.json.get('area_two_id')
  area_one_id = request.json.get('area_one_id')
  country_id = request.json.get('country_id')

  sd_data = ShoreDivingData.query.filter_by(id=id).first()
  if sd_data:
    if sd_data.name:
      abort(409, 'Already exists')
    else:
      sd_data.name=name
      sd_data.name_url=name_url
      sd_data.destination=destination
      sd_data.destination_url=destination_url
      sd_data.region=region
      sd_data.region_url=region_url
      db.session.add(sd_data)
      db.session.commit()
      sd_data.id
      return { 'data': sd_data.get_dict() }

  spot = Spot(
    name=name,
    location_city=location_city,
    description=description + '\n\n' + directions,
    is_verified=True,
    country_id=country_id,
    area_one_id=area_one_id,
    area_two_id=area_two_id,
  )

  sd_data = ShoreDivingData(
    id=id,
    name=name,
    name_url=name_url,
    destination=destination,
    destination_url=destination_url,
    region=region,
    region_url=region_url,
    spot=spot,
  )

  db.session.add(sd_data)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  return { 'data': spot.get_dict() }

@bp.route("/add/wdscript", methods=["POST"])
def add_spot_wdscript():
  name = request.json.get('name')
  description = request.json.get('description')
  directions = request.json.get('directions')
  url = request.json.get('url')
  location_city = request.json.get('location_city')
  alternative = request.json.get('alternative')
  latitude = request.json.get('latitude')
  longitude = request.json.get('longitude')
  max_depth = request.json.get('max_depth')
  difficulty = request.json.get('difficulty') if request.json.get('difficulty') != 'null' else None
  tags = request.json.get('tags') if request.json.get('tags') else []

  sd_data = WannaDiveData.query.filter_by(url=url).first()
  if sd_data:
    abort(409, 'Already exists')

  full_description = description + '\n\n' + directions
  if alternative:
    full_description += '\n\n%(title)s is also known as %(alternative)s.' % { 'title':name, 'alternative':alternative }

  spot = Spot(
    name=name,
    location_city=location_city,
    description=full_description,
    is_verified=True,
    latitude=latitude,
    longitude=longitude,
    max_depth=max_depth,
    difficulty=difficulty,
  )

  sd_data = WannaDiveData(
    url=url,
    spot=spot,
  )

  for tag_text in tags:
    tag = Tag.query.filter(and_(Tag.text==tag_text, Tag.type=='Access')).first()
    if not tag:
      tag = Tag(
        text=tag_text,
        type='Access',
      )
    spot.tags.append(tag)

  db.session.add(spot)
  db.session.add(sd_data)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  return { 'data': spot.get_dict() }

@bp.route("/add/tags", methods=["POST"])
def add_spot_tags():
  url = request.args.get('url')
  sd_data = WannaDiveData.query.filter_by(url=url).first()
  if sd_data:
    abort(400, 'Already exists')

  spot = sd_data.spot

  for tag in tags:
    tag = Tag.query.filter(and_(Tag.text==tag.text, Tag.type==tag.type)).first()
    if not tag:
      tag = Tag(
        text=tag.text,
        type=tag.type,
      )
    spot.tags.append(tag)

  db.session.add(spot)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  return { 'data': spot.get_dict() }

# @bp.route("tag/shore", methods=["POST"])
# def tag_shore_spots():
#   tag = Tag.query.filter(and_(Tag.text=='shore', Tag.type=='Access')).first()
#   if not tag:
#     tag = Tag(
#       text='shore',
#       type='Access',
#     )
#   spots = ShoreDivingData.query.all()
#   for sd_spot in spots:
#     sd_spot.spot.tags.append(tag)
#   db.session.commit()
#   return { 'data': len(spots) }

# @bp.route("/fix_tags")
# def tag_fix():
#   good_short_tag = Tag.query.filter_by(id=1).first()
#   remove_shore_tag = Tag.query.filter_by(id=2).first()
#   spots = Spot.query.filter(Spot.tags.any(id=2)).all()
#   edited_spots = []
#   for spot in spots:
#     if len(spot.tags)>=2:
#       if spot.tags[0].text == spot.tags[1].text:
#         spot.tags.remove(remove_shore_tag)
#         edited_spots.append(spot.get_dict())
#     elif len(spot.tags)==1:
#       if spot.tags[0].id==2:
#         spot.tags.append(good_short_tag)
#         spot.tags.remove(remove_shore_tag)
#         edited_spots.append(spot.get_dict())
#     db.session.commit()
#   return { 'num_spots': len(spots), 'data': edited_spots }

@bp.route("/add", methods=["POST"])
@jwt_required(optional=True)
def add_spot():
  """ Add Spot
  ---
  post:
      summary: Add Spot
      description: Add Spot
      parameters:
          - name: name
            in: body
            description: name
            type: string
            required: true
      responses:
          200:
              description: Returns singular beach object or list of beach objects
              content:
                application/json:
                  schema: BeachSchema
  """
  name = request.json.get('name')
  location_city = request.json.get('location_city')
  description = request.json.get('description')
  location_google = request.json.get('location_google')
  hero_img = request.json.get('hero_img')
  entry_map = request.json.get('entry_map')
  place_id = request.json.get('place_id')
  max_depth = request.json.get('max_depth')
  difficulty = request.json.get('difficulty')
  latitude = request.json.get('latitude')
  longitude = request.json.get('longitude')
  user = get_current_user()
  is_verified = True if user and user.admin else False

  if not name or not location_city:
    abort(422, 'Please enter a name and location')

  spot = Spot.query.filter(and_(Spot.name==name, Spot.location_city==location_city)).first()
  if spot:
    abort(409, 'Spot already exists')

  locality, area_2, area_1, country, latitude, longitude = None, None, None, None, None, None
  if place_id and not location_google:
    r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params = {
      'place_id': place_id,
      'fields': 'name,geometry,address_components,url',
      'key': os.environ.get('GOOGLE_API_KEY')
    })
    response = r.json()
    if response.get('status') == 'OK':
      result = response.get('result')
      if latitude and longitude:
        location_google = 'http://maps.google.com/maps?q={latitude},{longitude}' \
          .format(latitude=latitude, longitude=longitude)
      else:
        location_google = result.get('url')
        latitude = result.get('geometry').get('location').get('lat')
        longitude = result.get('geometry').get('location').get('lng')
      address_components = result.get('address_components')
      locality, area_2, area_1, country = get_localities(address_components)

  spot = Spot(
    name=name,
    location_city=location_city,
    description=description,
    location_google=location_google,
    hero_img=hero_img,
    entry_map=entry_map,
    is_verified=is_verified,
    submitter=user,
    google_place_id=place_id,
    latitude=latitude,
    longitude=longitude,
    max_depth=max_depth,
    difficulty=difficulty,
  )
  spot.locality = locality
  spot.area_one = area_1
  spot.area_two = area_2
  spot.country = country
  db.session.add(spot)
  db.session.commit()
  spot.id #need this to get data loaded, not sure why
  if not user or not user.admin:
    message = Mail(
        from_email=('hello@zentacle.com', 'Zentacle'),
        to_emails=['mayank@zentacle.com', 'cayley@zentacle.com'])

    message.template_id = 'd-df22c68e00c345108a3ac18ebf65bdaf'
    message.dynamic_template_data = {
        'beach_name': spot.name,
        'user_display_name': 'Logged out user',
        'description': description,
        'location': location_city,
        'url': 'https://www.zentacle.com'+spot.get_url(),
        'approve_url': 'https://www.zentacle.com/api/spots/approve?id='+str(spot.id),
    }
    if not os.environ.get('FLASK_DEBUG'):
      try:
          sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
          sg.send(message)
      except Exception as e:
          newrelic.agent.record_exception(e)
          print(e.body)
  if user:
    message = Mail(
        from_email=('hello@zentacle.com', 'Zentacle'),
        to_emails=user.email)
    message.reply_to = 'mayank@zentacle.com'
    message.template_id = 'd-2280f0af94dd4a93aea15c5ec95e1760'
    message.dynamic_template_data = {
        'beach_name': spot.name,
        'first_name': user.first_name,
        'url': 'https://www.zentacle.com'+spot.get_url(),
    }
    if not os.environ.get('FLASK_DEBUG'):
      try:
          sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
          sg.send(message)
      except Exception as e:
          print(e.body)
  return { 'data': spot.get_dict() }, 200

@bp.route("/approve", methods=["GET"])
@jwt_required()
def approve_spot():
  if not get_current_user().admin:
    abort(401, 'Only admins can do that')
  beach_id = request.args.get('id')
  spot = Spot.query.filter_by(id=beach_id).first_or_404()
  if spot.is_verified:
    spot_data = spot.get_dict()
    spot_data['submitter'] = {}
    return { 'data': spot_data, 'status': 'already verified' }
  spot.is_verified = True
  db.session.commit()
  spot.id
  user = spot.submitter
  if user:
    message = Mail(
        from_email=('hello@zentacle.com', 'Zentacle'),
        to_emails=user.email)
    message.reply_to = 'mayank@zentacle.com'
    message.template_id = 'd-7b9577485616413c95f6d7e2829c52c6'
    message.dynamic_template_data = {
        'beach_name': spot.name,
        'first_name': user.first_name,
        'url': 'https://www.zentacle.com'+spot.get_url()+'/review',
    }
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        newrelic.agent.record_exception(e)
        print(e.body)
  spot_data = spot.get_dict()
  spot_data['submitter'] = {}
  return { 'data': spot_data }, 200

@bp.route("/patch", methods=["PATCH"])
@jwt_required()
def patch_spot():
  """ Patch Beach
    ---
    patch:
        summary: patch beach (admin only)
        description: patch beach (admin only). also include the params of the beach that you want to change in the body
        parameters:
          - name: id
            in: body
            description: beach id
            type: int
            required: true
        responses:
            200:
                description: Returns Beach object
                content:
                  application/json:
                    schema: BeachSchema
            400:
                content:
                  application/json:
                    schema:
                      Error:
                        properties:
                          msg:
                            type: string
                description: Not logged in.
  """
  if not get_current_user().admin:
    abort(401, 'Only admins can do that')
  beach_id = request.json.get('id')
  spot = Spot.query.filter_by(id=beach_id).first_or_404()
  updates = request.json
  updates.pop('id', None)
  for key in updates.keys():
    setattr(spot, key, updates.get(key))
    if key == 'google_place_id':
      place_id = updates.get(key)
      if place_id == 'na':
        continue
      r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params = {
        'place_id': place_id,
        'fields': 'name,geometry,url,address_components',
        'key': os.environ.get('GOOGLE_API_KEY')
      })
      response = r.json()
      if response.get('status') == 'OK':
        if not updates.get('latitude') or not updates.get('longitude'):
          latitude = response.get('result').get('geometry').get('location').get('lat')
          longitude = response.get('result').get('geometry').get('location').get('lng')
          url = response.get('result').get('url')
          spot.latitude = latitude
          spot.longitude = longitude
          spot.location_google = url
        address_components = response.get('result').get('address_components')
        locality, area_2, area_1, country = get_localities(address_components)
        spot.locality = locality
        spot.area_one = area_1
        spot.area_two = area_2
        spot.country = country
        db.session.add(spot)
        db.session.commit()
      spot.id
  if updates.get('latitude') and updates.get('longitude'):
    latitude = updates.get('latitude')
    longitude = updates.get('longitude')
    spot.location_google = 'http://maps.google.com/maps?q={latitude},{longitude}' \
      .format(latitude=latitude, longitude=longitude)
  db.session.commit()
  spot.id
  spot_data = spot.get_dict()
  return spot_data, 200

@bp.route("/delete")
def delete_spot():
  id = request.args.get('id')

  beach = Spot.query \
    .filter_by(id=id) \
    .options(joinedload(Spot.images)) \
    .first_or_404()
  for image in beach.images:
    Image.query.filter_by(id=image.id).delete()
  for review in beach.reviews:
    Review.query.filter_by(id=review.id).delete()

  if beach.shorediving_data:
    ShoreDivingData.query.filter_by(id=beach.shorediving_data.id).delete()

  Spot.query.filter_by(id=id).delete()
  db.session.commit()
  return {}

@bp.route("/recs")
@jwt_required(optional=True)
def get_recs():
  """ Recommended Sites
  ---
  get:
      summary: Recommended Sites
      description: Recommended sites for a specific user based on where they have already visited
      parameters:
          - name: lat
            in: query
            description: latitude as a decimal
            type: number
            required: false
          - name: lng
            in: query
            description: longitude as a decimal
            type: number
            required: false
      responses:
          200:
              description: Returns array of beaches/dive sites
              content:
                application/json:
                  schema: BeachSchema
  """
  user_id = get_jwt_identity()
  if not user_id:
    return { 'data': {} }, 401
  # (SELECT * FROM SPOT a LEFT JOIN REVIEW b ON a.id = b.beach_id WHERE b.author_id = user_id) as my_spots
  # SELECT * FROM SPOT A LEFT JOIN my_spots B ON A.id = B.id WHERE b.id IS NULL
  spots_been_to = db.session.query(Spot.id) \
    .join(Review, Spot.id == Review.beach_id, isouter=True) \
    .filter(Review.author_id==user_id).subquery()
  spots = Spot.query \
    .filter(Spot.id.not_in(spots_been_to)) \
    .filter(Spot.is_verified.isnot(False)) \
    .filter(Spot.is_deleted.isnot(True)) \
    .order_by(Spot.num_reviews.desc().nullslast(), Spot.rating.desc()) \
    .limit(25) \
    .all()
  data = []
  for spot in spots:
    data.append(spot.get_dict())

  return { 'data': data }

@bp.route("/nearby")
@cache.cached(query_string=True)
def nearby_locations():
  """ Nearby Locations
  ---
  post:
      summary: Nearby locations given a specific dive site
      description: Nearby locations given a specific dive site
      parameters:
          - name: beach_id
            in: body
            description: beach_id
            type: integer
            required: true
      responses:
          200:
              description: Returns list of beach objects
              content:
                application/json:
                  schema: BeachSchema
          400:
              content:
                application/json:
                  schema:
                    msg: string
              description: No lat/lng or other location data found for given location
  """
  startlat = request.args.get('lat')
  startlng = request.args.get('lng')
  limit = request.args.get('limit') if request.args.get('limit') else 10
  spot_id = None
  if not startlat or not startlng:
    beach_id = request.args.get('beach_id')
    if not beach_id:
      abort(422, 'Include a lat/lng or a beach_id')
    spot = Spot.query \
      .options(joinedload(Spot.shorediving_data)) \
      .filter_by(id=beach_id) \
      .first_or_404()
    startlat = spot.latitude
    startlng = spot.longitude
    spot_id = spot.id

  if not startlat or not startlng:
    spots = []
    if spot.shorediving_data:
      try:
        spots = Spot.query \
          .filter(Spot.shorediving_data.has(destination_url=spot.shorediving_data.destination_url)) \
          .limit(limit) \
          .all()
      except AttributeError as e:
        newrelic.agent.record_exception(e)
        return { 'msg': str(e) }
    else:
      try:
        spots = Spot.query.filter(Spot.has(country_id=spot.country_id)).limit(limit).all()
      except AttributeError as e:
        newrelic.agent.record_exception(e)
        return { 'msg': str(e) }
    output=[]
    for spot in spots:
      spot_data = spot.get_dict()
      output.append(spot_data)
    if len(output):
      return { 'data': output }
    else:
      abort(400, 'No lat/lng, country_id, or sd_data for this spot')

  results = get_nearby_spots(startlat, startlng, limit, spot_id)
  data = []
  for result in results:
    temp_data = result.get_dict()
    if result.locality and result.locality.url:
      temp_data['locality'] = {
        'url': result.locality.url
      }
    else:
      temp_data.pop('locality', None)
    data.append(temp_data)
  return { 'data': data }

@bp.route("/location")
def get_location_spots():
  type = request.args.get('type')
  name = request.args.get('name')
  locality = None
  if type == 'locality':
    locality = Locality.query.filter_by(name=name).first_or_404()
  if type == 'area_one':
    locality = AreaOne.query.filter_by(name=name).first_or_404()
  if type == 'area_two':
    locality = AreaTwo.query.filter_by(name=name).first_or_404()
  if type == 'country':
    locality = Country.query.filter_by(name=name).first_or_404()
  data = []
  for spot in locality.spots:
    data.append(spot.get_dict())
  return { 'data': data }

@bp.route("/add_place_id", methods=["POST"])
def add_place_id():
  spots = Spot.query.filter(Spot.is_verified.isnot(False)).all()
  skipped = []
  for spot in spots:
    if spot.google_place_id and spot.google_place_id != "na":
      place_id = spot.google_place_id
      r = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params = {
          'place_id': place_id,
          'fields': 'address_components',
          'key': os.environ.get('GOOGLE_API_KEY')
        })
      response = r.json()
      if response.get('status') == 'OK':
        address_components = response.get('result').get('address_components')
        locality, area_2, area_1, country = get_localities(address_components)
        spot.locality = locality
        spot.area_one = area_1
        spot.area_two = area_2
        spot.country = country
        db.session.add(spot)
        db.session.commit()
        spot.id
      else:
        skipped.append({'name': spot.name})
    else:
      skipped.append({'name': spot.name})
  return { 'data': skipped }

@bp.route("/patch/shorediving", methods=["POST"])
def add_shorediving_pic():
  id = request.json.get('id')
  pic_url = request.json.get('url')

  shorediving = ShoreDivingData.query.filter_by(id=id).first_or_404()
  if not shorediving.spot.hero_img:
    shorediving.spot.hero_img = 'https://'+os.environ.get('S3_BUCKET_NAME')+'.s3.amazonaws.com/' + pic_url
  else:
    abort(401, 'Location already has a hero image')
  db.session.commit()
  shorediving.spot.id
  return { 'data': shorediving.spot.get_dict() }

@bp.route("/add/shoredivingdata", methods=["POST"])
def add_shorediving_to_existing():
  beach_id = request.json.get('beach_id')
  sd_id = request.json.get('sd_id')
  spot = Spot.query.filter_by(id=beach_id).first_or_404()
  sd_data = ShoreDivingData(
    id=sd_id,
    spot=spot,
  )
  db.session.add(sd_data)
  db.session.commit()
  sd_data.id
  return { 'data': sd_data.get_dict() }

@bp.route("/add/backfill", methods=["POST"])
def backfill_shorediving_to_existing():
  name = request.json.get('name')
  id = request.json.get('id')
  name_url = request.json.get('name_url')
  destination = request.json.get('destination')
  destination_url = request.json.get('destination_url')
  region = request.json.get('region')
  region_url = request.json.get('region_url')
  area_two_id = request.json.get('area_two_id')

  spot = Spot.query.filter_by(name=name).first_or_404()
  if spot.area_two_id != area_two_id:
    abort(401, 'Couldnt find a spot in the correct region with this name')

  sd_spot = ShoreDivingData.query.filter_by(id=id).first()
  if sd_spot:
    abort(402, 'Already exists')

  sd_data = ShoreDivingData(
    id=id,
    name=name,
    name_url=name_url,
    destination=destination,
    destination_url=destination_url,
    region=region,
    region_url=region_url,
    spot=spot,
  )
  db.session.add(sd_data)
  db.session.commit()
  sd_data.id
  return { 'data': sd_data.get_dict() }

@bp.route("/merge", methods=["POST"])
def merge_spot():
  orig_id = request.json.get('orig_id')
  dupe_id = request.json.get('dupe_id')
  orig = Spot.query.filter_by(id=orig_id).first_or_404()
  dupe = Spot.query.filter_by(id=dupe_id).first_or_404()
  wd_data = WannaDiveData.query.filter_by(spot_id=dupe_id).first()
  if wd_data:
    wd_data.spot_id = orig.id
  if not orig.latitude or not orig.longitude:
    orig.latitude = dupe.latitude
    orig.longitude = dupe.longitude
  if not orig.difficulty:
    orig.difficulty = dupe.difficulty
  if not orig.max_depth:
    orig.max_depth = dupe.max_depth
  if not orig.rating:
    orig.rating = dupe.rating
  if not orig.last_review_viz:
    orig.last_review_viz = dupe.last_review_viz
  for tag in dupe.tags:
    if tag not in orig.tags:
      orig.tags.append(tag)
  dupe.is_deleted = True
  db.session.commit()
  orig.id
  return { 'data': orig.get_dict() }