"""Build and look up Places (see LOCATION_MIGRATION.md)."""

from collections import Counter

from app.helpers.demicrosoft import demicrosoft
from app.models import AreaOne, AreaTwo, Country, DiveShop, Locality, Place, PlaceRedirect, Spot, db

LEGACY_MODELS = [
    ("country", Country, "country"),
    ("area_one", AreaOne, "region"),
    ("area_two", AreaTwo, "county"),
    ("locality", Locality, "city"),
]

# For each legacy level, its possible parents, nearest first. A missing (or
# unusable) parent is skipped, so a town with no county hangs off its region.
PARENT_COLUMNS = {
    "country": [],
    "area_one": [("country", "country_id")],
    "area_two": [("area_one", "area_one_id"), ("country", "country_id")],
    "locality": [("area_two", "area_two_id"), ("area_one", "area_one_id"), ("country", "country_id")],
}


def get_place_by_path(path):
    """The place whose public URL is `path` (e.g. "/loc/pt/beja/_/vila-nova")."""
    return Place.query.filter_by(path=path.rstrip("/")).first()


def legacy_slug(row):
    """A legacy row's URL slug, or None if it has no usable ASCII form (e.g. a
    name only in Arabic or Chinese script, or a short_name of "-")."""
    return demicrosoft(row.short_name or "").lower() or demicrosoft(row.name or "").lower() or None


def is_valid_path(path):
    """A /loc/... path whose every segment is a real slug."""
    if not path or not path.startswith("/loc/"):
        return False
    segments = path[len("/loc/") :].split("/")
    return all(segments) and "None" not in segments


def computed_url(legacy_type, row):
    """The legacy-style URL for a row from its own relations, with "_" for a
    missing (or unusable) level: the same shape the legacy code builds."""
    country = row if legacy_type == "country" else row.country
    country_slug = legacy_slug(country) if country else None
    if not country_slug:
        return None
    if legacy_type == "country":
        return f"/loc/{country_slug}"

    def part(parent):
        return (legacy_slug(parent) if parent else None) or "_"

    own = legacy_slug(row)
    if not own:
        return None
    if legacy_type == "area_one":
        return f"/loc/{country_slug}/{own}"
    if legacy_type == "area_two":
        return f"/loc/{country_slug}/{part(row.area_one)}/{own}"
    return f"/loc/{country_slug}/{part(row.area_one)}/{part(row.area_two)}/{own}"


def legacy_url(legacy_type, row):
    """The URL to keep for a legacy row: the one the legacy API serves today
    when it's valid, otherwise one computed from the row's relations. Stored
    URLs can be empty or broken (e.g. "/loc/pr/None/_/san-juan")."""
    served = row.get_dict().get("url") or row.url
    if is_valid_path(served):
        return served
    computed = computed_url(legacy_type, row)
    return computed if is_valid_path(computed) else None


def build_places_from_legacy(apply=False):
    """Create or update one Place per legacy location row, then point every
    spot and shop at its most specific place.

    - Levels that are missing, or unusable (no Latin-script slug), are
      skipped: their children hang off the nearest usable ancestor, and their
      spots go to that ancestor too.
    - The same place stored twice under one parent (same slug, e.g. Kaafu
      Atoll as both a region and a county) becomes one place; the duplicate's
      URL is recorded as a PlaceRedirect to it.

    Idempotent: places are matched on (legacy_type, legacy_id) and an existing
    place's path is never changed. Runs in a transaction that is rolled back
    unless apply=True, so a dry run reports exactly what an apply would do.
    """
    report = Counter(created=0, updated=0, moved=0, redirects_added=0)
    problems = {"no_country": [], "unusable": [], "merged": []}

    all_places = Place.query.all()
    places = {(p.legacy_type, p.legacy_id): p for p in all_places if p.legacy_type}
    by_path = {p.path: p for p in all_places}
    by_slug = {(p.parent_id, p.slug): p for p in all_places}
    redirect_paths = {path for (path,) in db.session.query(PlaceRedirect.path)}

    def add_redirect(path, place, reason):
        if is_valid_path(path) and path != place.path and path not in by_path and path not in redirect_paths:
            db.session.add(PlaceRedirect(path=path, place=place, reason=reason))
            redirect_paths.add(path)
            report["redirects_added"] += 1

    for legacy_type, model, kind in LEGACY_MODELS:
        for row in model.query.order_by(model.id).all():
            key = (legacy_type, row.id)
            parent = None
            for parent_type, column in PARENT_COLUMNS[legacy_type]:
                parent_id = getattr(row, column)
                if parent_id and (parent_type, parent_id) in places:
                    parent = places[(parent_type, parent_id)]
                    break
            if legacy_type != "country" and parent is None:
                problems["no_country"].append(key)
                continue

            place = places.get(key)
            if place and (place.legacy_type, place.legacy_id) == key:
                place.name = row.name
                place.google_name = getattr(row, "google_name", None)
                place.description = row.description or place.description
                place.map_image_url = row.map_image_url or place.map_image_url
                if place.parent_id != (parent.id if parent else None):
                    place.move_to(parent)
                    report["moved"] += 1
                report["updated"] += 1
                continue

            slug = legacy_slug(row)
            url = legacy_url(legacy_type, row)
            if not slug or not url:
                problems["unusable"].append((key, row.name))
                continue

            existing = by_path.get(url) or by_slug.get((parent.id if parent else None, slug))
            if existing:
                # the same place stored twice: map this row onto the first one
                places[key] = existing
                add_redirect(url, existing, "merged_duplicate")
                problems["merged"].append((key, url, existing.path))
                continue

            place = Place.create(
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
            places[key] = by_path[url] = by_slug[(place.parent_id, slug)] = place
            report["created"] += 1

    for model, label in ((Spot, "spots"), (DiveShop, "shops")):
        report[f"{label}_assigned"] += 0
        report[f"{label}_unplaced"] += 0
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

    return {"applied": apply, **report, **problems}


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
