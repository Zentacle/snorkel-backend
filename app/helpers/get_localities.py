from sqlalchemy import and_, or_, sql

from app.models import AreaOne, AreaTwo, Country, Locality, db

from .demicrosoft import demicrosoft


def format_localities(address_components):
    formatted_output = {}
    for component in address_components:
        if "locality" in component.get("types"):
            formatted_output["locality"] = component
        if "administrative_area_level_1" in component.get("types"):
            formatted_output["area_1"] = component
        if "administrative_area_level_2" in component.get("types"):
            formatted_output["area_2"] = component
        if "country" in component.get("types"):
            formatted_output["country"] = component
    return formatted_output


def _slug(component):
    """URL slug for a Google address component, or None when it has no usable
    ASCII form (e.g. a name only in Arabic or Chinese script)."""
    for key in ("short_name", "long_name"):
        slug = demicrosoft(component.get(key) or "").lower()
        if slug:
            return slug
    return None


def _same_parent(column, parent):
    """Filter on a parent foreign key that also matches "no parent"."""
    if parent is None:
        return column.is_(None)
    if parent.id is None:  # created in this call: no existing children yet
        return sql.false()
    return column == parent.id


def get_localities(address_components):
    """Find or create the Country/AreaOne/AreaTwo/Locality rows for a Google
    geocoding result. Returns (locality, area_two, area_one, country); levels
    Google doesn't provide (or that have no usable slug) are None."""
    components = format_localities(address_components)
    country_component = components.get("country")
    country_slug = _slug(country_component) if country_component else None
    if not country_slug:
        return None, None, None, None

    country = Country.query.filter_by(short_name=country_slug).first()
    if not country:
        country = Country(
            name=country_component.get("long_name"),
            short_name=country_slug,
            url=f"/loc/{country_slug}",
        )
        db.session.add(country)
    in_country = country.short_name

    area_1 = None
    area_1_component = components.get("area_1")
    area_1_slug = _slug(area_1_component) if area_1_component else None
    if area_1_slug:
        area_1 = AreaOne.query.filter(
            and_(AreaOne.short_name == area_1_slug, AreaOne.country.has(short_name=in_country))
        ).first()
        if not area_1:
            area_1 = AreaOne(
                name=area_1_component.get("long_name"),
                country=country,
                short_name=area_1_slug,
                url=f"/loc/{in_country}/{area_1_slug}",
            )
            db.session.add(area_1)
    # missing levels are "_" in URLs
    area_1_path = area_1.short_name if area_1 else "_"

    area_2 = None
    area_2_component = components.get("area_2")
    area_2_slug = _slug(area_2_component) if area_2_component else None
    if area_2_slug:
        area_2_name = area_2_component.get("long_name")
        area_2_url = f"/loc/{in_country}/{area_1_path}/{area_2_slug}"
        area_2 = AreaTwo.query.filter(
            or_(
                and_(
                    AreaTwo.google_name == area_2_name,
                    AreaTwo.country.has(short_name=in_country),
                    _same_parent(AreaTwo.area_one_id, area_1),
                ),
                AreaTwo.url == area_2_url,
            )
        ).first()
        if not area_2:
            area_2 = AreaTwo(
                google_name=area_2_name,
                name=area_2_name,
                area_one=area_1,
                country=country,
                short_name=area_2_slug,
                url=area_2_url,
            )
            db.session.add(area_2)
    area_2_path = area_2.short_name if area_2 else "_"

    locality = None
    locality_component = components.get("locality")
    locality_slug = _slug(locality_component) if locality_component else None
    if locality_slug:
        locality_name = locality_component.get("long_name")
        locality_url = f"/loc/{in_country}/{area_1_path}/{area_2_path}/{locality_slug}"
        locality = Locality.query.filter(
            or_(
                and_(
                    Locality.google_name == locality_name,
                    Locality.country.has(short_name=in_country),
                    _same_parent(Locality.area_one_id, area_1),
                ),
                Locality.url == locality_url,
            )
        ).first()
        if not locality:
            locality = Locality(
                google_name=locality_name,
                name=locality_name,
                short_name=locality_slug,
                area_one=area_1,
                area_two=area_2,
                country=country,
                url=locality_url,
            )
            db.session.add(locality)

    return (locality, area_2, area_1, country)
