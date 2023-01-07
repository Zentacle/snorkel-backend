from app.models import *
from .demicrosoft import demicrosoft
from sqlalchemy import and_

def format_localities(address_components):
  formatted_output = {}
  for component in address_components:
    if 'locality' in component.get('types'):
      formatted_output['locality'] = component
    if 'administrative_area_level_1' in component.get('types'):
      formatted_output['area_1'] = component
    if 'administrative_area_level_2' in component.get('types'):
      formatted_output['area_2'] = component
    if 'country' in component.get('types'):
      formatted_output['country'] = component
  return formatted_output

def get_localities(address_components):
  locality_name = None
  area_1_name = None
  area_2_name = None
  country_name = None
  area_1_short_name = None
  area_2_short_name = None
  country_short_name = None
  for component in address_components:
    if 'locality' in component.get('types'):
      locality_name = component.get('long_name')
      locality_short_name = demicrosoft(component.get('short_name').lower())
    if 'administrative_area_level_1' in component.get('types'):
      area_1_name = component.get('long_name')
      area_1_short_name = demicrosoft(component.get('short_name').lower())
    if 'administrative_area_level_2' in component.get('types'):
      area_2_name = component.get('long_name')
      area_2_short_name = demicrosoft(component.get('short_name').lower())
    if 'country' in component.get('types'):
      country_name = component.get('long_name')
      country_short_name = demicrosoft(component.get('short_name').lower())
  country = Country.query.filter_by(short_name=country_short_name).first()
  if not country:
    country = Country(
      name=country_name,
      short_name=country_short_name,
      url=f'/loc/{country_short_name}',
    )
  area_1 = AreaOne.query \
    .filter(
      and_(
        AreaOne.short_name==area_1_short_name,
        AreaOne.country.has(short_name=country.short_name)
    ))\
    .first()
  if not area_1 and area_1_name:
    area_1 = AreaOne(
      name=area_1_name,
      country=country,
      short_name=area_1_short_name,
      url=f'/loc/{country_short_name}/{area_1_short_name}',
    )
  area_2 = AreaTwo.query.filter_by(google_name=area_2_name).first()
  if not area_2 and area_2_name:
    area_1_short_name = area_1_short_name or '_'
    area_2 = AreaTwo(
      google_name=area_2_name,
      name=area_2_name,
      area_one=area_1,
      country=country,
      short_name=area_2_short_name,
      url=f'/loc/{country_short_name}/{area_1_short_name}/{area_2_short_name}',
    )
  locality = Locality.query.filter_by(google_name=locality_name).first()
  if not locality and locality_name:
    area_2_short_name = area_2_short_name or '_'
    locality = Locality(
      google_name=locality_name,
      name=locality_name,
      short_name=locality_short_name,
      area_one=area_1,
      area_two=area_2,
      country=country,
      url=f'/loc/{country_short_name}/{area_1_short_name}/{area_2_short_name}/{locality_short_name}',
    )
  return (locality, area_2, area_1, country)