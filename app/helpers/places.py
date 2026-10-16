"""Build and look up Places (see LOCATION_MIGRATION.md)."""

from collections import Counter

from app.models import AreaOne, AreaTwo, Country, DiveShop, Locality, Place, Spot, db

LEGACY_MODELS = [
    ("country", Country, "country"),
    ("area_one", AreaOne, "region"),
    ("area_two", AreaTwo, "county"),
    ("locality", Locality, "city"),
]


def get_place_by_path(path):
    """The place whose public URL is `path` (e.g. "/loc/pt/beja/_/vila-nova")."""
    return Place.query.filter_by(path=path.rstrip("/")).first()


def legacy_url(row):
    """The URL the legacy API serves for a Country/AreaOne/AreaTwo/Locality row
    today, "_" gaps included."""
    return row.get_dict().get("url") or row.url


def _legacy_parent_key(legacy_type, row):
    """(legacy_type, id) of the nearest existing legacy ancestor. Missing
    levels are skipped, so a town with no county hangs off its region."""
    if legacy_type == "locality":
        if row.area_two_id:
            return ("area_two", row.area_two_id)
    if legacy_type in ("locality", "area_two") and row.area_one_id:
        return ("area_one", row.area_one_id)
    if legacy_type != "country" and row.country_id:
        return ("country", row.country_id)
    return None


def build_places_from_legacy(apply=False):
    """Create or update one Place per legacy location row, then point every
    spot and shop at its most specific place.

    Idempotent: places are matched on (legacy_type, legacy_id), and an
    existing place's path is never changed. Runs in a transaction that is
    rolled back unless apply=True, so a dry run reports exactly what an
    apply would do. Rows that can't be placed are reported, not guessed.
    """
    report = Counter()
    problems = {"no_country": [], "no_url": [], "duplicate_path": [], "duplicate_slug": []}

    existing = {(p.legacy_type, p.legacy_id): p for p in Place.query.filter(Place.legacy_type.isnot(None))}
    taken_paths = {p.path for p in Place.query.with_entities(Place.path)}
    taken_slugs = {(p.parent_id, p.slug) for p in Place.query.with_entities(Place.parent_id, Place.slug)}
    places = dict(existing)

    for legacy_type, model, kind in LEGACY_MODELS:
        for row in model.query.order_by(model.id).all():
            key = (legacy_type, row.id)
            parent_key = _legacy_parent_key(legacy_type, row)
            if legacy_type != "country" and not parent_key:
                problems["no_country"].append(key)
                continue
            parent = places.get(parent_key) if parent_key else None
            if parent_key and not parent:
                problems["no_country"].append(key)  # its ancestor couldn't be placed
                continue

            place = places.get(key)
            if place:
                place.name = row.name
                place.google_name = getattr(row, "google_name", None)
                place.description = row.description or place.description
                place.map_image_url = row.map_image_url or place.map_image_url
                if place.parent_id != (parent.id if parent else None):
                    place.move_to(parent)
                    report["moved"] += 1
                report["updated"] += 1
                continue

            url = legacy_url(row)
            slug = row.short_name.lower() if row.short_name else None
            if not url or not url.startswith("/loc/") or not slug:
                problems["no_url"].append(key)
                continue
            if url in taken_paths:
                problems["duplicate_path"].append((key, url))
                continue
            if (parent.id if parent else None, slug) in taken_slugs:
                problems["duplicate_slug"].append((key, url))
                continue

            places[key] = Place.create(
                name=row.name,
                slug=slug,
                kind=kind,
                parent=parent,
                path=url,
                google_name=getattr(row, "google_name", None),
                description=row.description,
                map_image_url=row.map_image_url,
                country_code=slug.upper() if legacy_type == "country" and len(slug) == 2 else None,
                legacy_type=legacy_type,
                legacy_id=row.id,
            )
            taken_paths.add(url)
            taken_slugs.add((parent.id if parent else None, slug))
            report["created"] += 1

    for model, label in ((Spot, "spots"), (DiveShop, "shops")):
        for item in model.query.all():
            place = _most_specific_place(item, places)
            if place is None:
                report[f"{label}_unplaced"] += 1
            elif item.place_id != place.id:
                item.place_id = place.id
                report[f"{label}_assigned"] += 1

    if apply:
        db.session.commit()
    else:
        db.session.rollback()

    return {"applied": apply, **report, **{name: rows for name, rows in problems.items()}}


def _most_specific_place(item, places):
    for legacy_type, column in (
        ("locality", "locality_id"),
        ("area_two", "area_two_id"),
        ("area_one", "area_one_id"),
        ("country", "country_id"),
    ):
        legacy_id = getattr(item, column)
        if legacy_id and (legacy_type, legacy_id) in places:
            return places[(legacy_type, legacy_id)]
    return None
