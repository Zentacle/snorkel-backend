from app.models import *
from .demicrosoft import demicrosoft

def get_localities(address_components):
  locality_name = None
  area_1_name = None
  area_2_name = None
  country_name = None
  for component in address_components:
    if 'locality' in component.get('types'):
      locality_name = component.get('long_name')
    if 'administrative_area_level_1' in component.get('types'):
      area_1_name = component.get('long_name')
      area_1_short_name = demicrosoft(component.get('short_name').lower())
    if 'administrative_area_level_2' in component.get('types'):
      area_2_name = component.get('long_name')
      area_2_short_name = demicrosoft(component.get('short_name').lower())
    if 'country' in component.get('types'):
      country_name = component.get('long_name')
      country_short_name = demicrosoft(component.get('short_name').lower())
  country = Country.query.filter_by(name=country_name).first()
  if not country:
    country = Country(
      name=country_name,
      short_name=country_short_name,
    )
  area_1 = AreaOne.query.filter_by(name=area_1_name).first()
  if not area_1:
    area_1 = AreaOne(
      name=area_1_name,
      country=country,
      short_name=area_1_short_name,
    )
  area_2 = AreaTwo.query.filter_by(google_name=area_2_name).first()
  if not area_2:
    area_2 = AreaTwo(
      google_name=area_2_name,
      name=area_2_name,
      area_one=area_1,
      country=country,
      short_name=area_2_short_name,
    )
  locality = Locality.query.filter_by(name=locality_name).first()
  if not locality:
    locality = Locality(
      name=locality_name,
      area_one=area_1,
      area_two=area_2,
      country=country,
    )
  return (locality, area_2, area_1, country)