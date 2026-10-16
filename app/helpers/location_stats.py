"""Aggregate stats for a location page (country / area_one / area_two / locality).

Built for SEO content: every value comes from our own data, and anything
with too few data points is left out (None) rather than guessed, so the
frontend can render a section only when it is backed by real numbers.
"""

import re
import statistics
from collections import Counter

from sqlalchemy import func

from app.models import AreaOne, AreaTwo, Country, DiveShop, Locality, Review, ShoreDivingReview, Spot, Tag, User, db
from app.models import tags as spot_tags

# Below this many data points an average or monthly value isn't shown.
MIN_SAMPLES = 3
# Below this many dated dives, "busiest months" isn't meaningful.
MIN_DIVES_FOR_SEASONALITY = 12
# A month counts as "busiest" with at least this multiple of the average.
BUSIEST_MONTH_FACTOR = 1.25
NUM_TOP_SPOTS = 5

# Review.visibility is a 1-5 rating (a handful of old rows hold feet; skip them).
VISIBILITY_RANGE = (1, 5)
# Water temps are stored in the author's units; discard implausible values.
WATER_TEMP_RANGE_F = (40, 100)
WATER_TEMP_RANGE_C = (4, 38)

SHOREDIVING_RATINGS = [
    "entry",
    "bottom",
    "reef",
    "animal",
    "plant",
    "facilities",
    "crowds",
    "roads",
    "snorkel",
    "beginner",
    "intermediate",
    "advanced",
    "night",
    "visibility",
    "current",
    "surf",
]

FEET_PER_METER = 3.28084


def _level_column(model, area):
    """The foreign key on Spot/DiveShop that points at this kind of area."""
    if isinstance(area, Locality):
        return model.locality_id
    if isinstance(area, AreaTwo):
        return model.area_two_id
    if isinstance(area, AreaOne):
        return model.area_one_id
    if isinstance(area, Country):
        return model.country_id
    raise ValueError(f"Unsupported area type: {type(area).__name__}")


def _rounded(value, digits=1):
    return round(value, digits) if value is not None else None


def parse_depth_ft(max_depth):
    """Spot.max_depth is free text, almost always "49.2 ft"; some use meters."""
    if not max_depth:
        return None
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(ft|feet|m|meters?)?\b", max_depth.lower())
    if not match:
        return None
    value = float(match.group(1))
    if match.group(2) and match.group(2).startswith("m"):
        value *= FEET_PER_METER
    return value if value > 0 else None


def water_temp_f(value, unit):
    """Normalize a review's water temp to °F using the author's unit setting."""
    if value is None:
        return None
    if unit == "metric":
        if not WATER_TEMP_RANGE_C[0] <= value <= WATER_TEMP_RANGE_C[1]:
            return None
        return value * 9 / 5 + 32
    if not WATER_TEMP_RANGE_F[0] <= value <= WATER_TEMP_RANGE_F[1]:
        return None
    return float(value)


def _f_to_c(value):
    return (value - 32) * 5 / 9 if value is not None else None


def _mean_or_none(values):
    return statistics.mean(values) if len(values) >= MIN_SAMPLES else None


def get_location_stats(area):
    spot_filter = [
        _level_column(Spot, area) == area.id,
        Spot.is_verified.isnot(False),
        Spot.is_deleted.isnot(True),
    ]
    spots = Spot.query.filter(*spot_filter).all()
    spot_ids = [spot.id for spot in spots]

    num_shops = db.session.query(func.count(DiveShop.id)).filter(_level_column(DiveShop, area) == area.id).scalar()

    # access (shore / boat) from tags
    access_rows = (
        db.session.query(Tag.short_name, func.count(spot_tags.c.spot_id))
        .join(spot_tags, spot_tags.c.tag_id == Tag.id)
        .filter(Tag.type == "Access", spot_tags.c.spot_id.in_(spot_ids))
        .group_by(Tag.short_name)
        .all()
        if spot_ids
        else []
    )

    difficulty = Counter((spot.difficulty or "unrated").lower() for spot in spots)

    depths = sorted(d for d in (parse_depth_ft(spot.max_depth) for spot in spots) if d)

    rated = [spot for spot in spots if spot.num_reviews and spot.rating]
    num_reviews = sum(spot.num_reviews for spot in rated)
    average_rating = sum(float(spot.rating) * spot.num_reviews for spot in rated) / num_reviews if num_reviews else None
    top_spots = sorted(rated, key=lambda spot: spot.get_confidence_score(), reverse=True)[:NUM_TOP_SPOTS]

    seasonality, visibility, water_temp = _review_stats(spot_ids)
    ratings_breakdown = _shorediving_ratings(spot_ids)

    last_review_dates = [spot.last_review_date for spot in spots if spot.last_review_date]

    return {
        "area": {"name": area.name, "url": area.get_dict().get("url"), "level": type(area).__name__.lower()},
        "num_spots": len(spots),
        "num_shops": num_shops,
        "num_reviews": num_reviews,
        "average_rating": _rounded(average_rating, 2),
        "access": {name: count for name, count in access_rows},
        "difficulty": dict(difficulty),
        "max_depth_ft": (
            {
                "min": _rounded(depths[0]),
                "max": _rounded(depths[-1]),
                "median": _rounded(statistics.median(depths)),
                "num_spots": len(depths),
            }
            if depths
            else None
        ),
        "top_spots": [spot.get_simple_dict() for spot in top_spots],
        "seasonality": seasonality,
        "visibility": visibility,
        "water_temp": water_temp,
        "ratings_breakdown": ratings_breakdown,
        "last_review_date": max(last_review_dates) if last_review_dates else None,
    }


def _review_stats(spot_ids):
    """Month-by-month dives, visibility (1-5) and water temp from reviews/dive logs."""
    if not spot_ids:
        return None, None, None

    rows = (
        db.session.query(Review.date_dived, Review.visibility, Review.water_temp, User.unit)
        .outerjoin(User, User.id == Review.author_id)
        .filter(Review.beach_id.in_(spot_ids), Review.is_private.isnot(True))
        .all()
    )

    dives_by_month = Counter()
    visibility_by_month = {month: [] for month in range(1, 13)}
    temp_by_month = {month: [] for month in range(1, 13)}
    for date_dived, viz, temp, unit in rows:
        month = date_dived.month if date_dived else None
        if month:
            dives_by_month[month] += 1
        if viz is not None and VISIBILITY_RANGE[0] <= viz <= VISIBILITY_RANGE[1] and month:
            visibility_by_month[month].append(viz)
        temp_f = water_temp_f(temp, unit)
        if temp_f is not None and month:
            temp_by_month[month].append(temp_f)

    all_viz = [v for values in visibility_by_month.values() for v in values]
    all_temps = [t for values in temp_by_month.values() for t in values]

    total_dives = sum(dives_by_month.values())
    seasonality = None
    if total_dives >= MIN_DIVES_FOR_SEASONALITY:
        months = []
        for month in range(1, 13):
            temp = _mean_or_none(temp_by_month[month])
            months.append(
                {
                    "month": month,
                    "num_dives": dives_by_month[month],
                    "avg_visibility": _rounded(_mean_or_none(visibility_by_month[month])),
                    "avg_water_temp_f": _rounded(temp),
                    "avg_water_temp_c": _rounded(_f_to_c(temp)),
                }
            )
        # up to 3 months clearly above the monthly average (ties at the
        # average don't count as "busiest")
        threshold = BUSIEST_MONTH_FACTOR * total_dives / 12
        busiest = sorted(
            (m for m in months if m["num_dives"] >= threshold),
            key=lambda m: m["num_dives"],
            reverse=True,
        )[:3]
        seasonality = {
            "num_dives": total_dives,
            "busiest_months": sorted(m["month"] for m in busiest),
            "months": months,
        }

    visibility = (
        {"average": _rounded(statistics.mean(all_viz)), "scale": 5, "num_reports": len(all_viz)}
        if len(all_viz) >= MIN_SAMPLES
        else None
    )
    average_temp = _mean_or_none(all_temps)
    water_temp = (
        {
            "average_f": _rounded(average_temp),
            "average_c": _rounded(_f_to_c(average_temp)),
            "min_f": _rounded(min(all_temps)),
            "max_f": _rounded(max(all_temps)),
            "num_reports": len(all_temps),
        }
        if average_temp is not None
        else None
    )
    return seasonality, visibility, water_temp


def _shorediving_ratings(spot_ids):
    """Average of each shorediving.com sub-rating (1-5) across the area's reviews."""
    if not spot_ids:
        return None
    columns = [getattr(ShoreDivingReview, name) for name in SHOREDIVING_RATINGS]
    rows = (
        db.session.query(*columns)
        .join(Review, Review.id == ShoreDivingReview.review_id)
        .filter(Review.beach_id.in_(spot_ids))
        .all()
    )
    breakdown = {}
    for i, name in enumerate(SHOREDIVING_RATINGS):
        # 0 / null means the reviewer didn't rate that aspect
        values = [row[i] for row in rows if row[i]]
        if len(values) >= MIN_SAMPLES:
            breakdown[name] = {"average": _rounded(statistics.mean(values)), "num_ratings": len(values)}
    return breakdown or None
