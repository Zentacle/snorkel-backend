from sqlalchemy import and_, sql
from sqlalchemy.orm import joinedload

from app.models import AreaOne, AreaTwo, Country, Locality


def get_area(country_name, area_one_name=None, area_two_name=None, locality_name=None):
    """Look up the location a /loc/... URL refers to, or 404.

    Returns the most specific match (Locality, AreaTwo, AreaOne or Country),
    or None when no country is given. "_" stands for a missing area_one or
    area_two in locality URLs.
    """
    if locality_name:
        area_two_area_query = Locality.area_two.has(short_name=area_two_name)
        area_one_area_query = Locality.area_one.has(short_name=area_one_name)
        if area_two_name == "_":
            area_two_area_query = sql.true()
        if area_one_name == "_":
            area_one_area_query = sql.true()
        return (
            Locality.query.options(joinedload("area_two"))
            .options(joinedload("area_one"))
            .options(joinedload("country"))
            .filter(
                Locality.short_name == locality_name,
                area_two_area_query,
                area_one_area_query,
                Locality.country.has(short_name=country_name),
            )
            .first_or_404()
        )
    if area_two_name:
        return (
            AreaTwo.query.options(joinedload("area_one"))
            .options(joinedload("country"))
            .filter(
                and_(
                    AreaTwo.short_name == area_two_name,
                    AreaTwo.area_one.has(short_name=area_one_name),
                    AreaTwo.country.has(short_name=country_name),
                )
            )
            .first_or_404()
        )
    if area_one_name:
        return (
            AreaOne.query.options(joinedload("country"))
            .filter(
                and_(
                    AreaOne.short_name == area_one_name,
                    AreaOne.country.has(short_name=country_name),
                )
            )
            .first_or_404()
        )
    if country_name:
        return Country.query.filter_by(short_name=country_name).first_or_404()
    return None
