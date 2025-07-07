import re

from flask import Blueprint, abort, request
from sqlalchemy import func, text
from sqlalchemy.orm import joinedload

from app import cache, db
from app.models import DiveShop, GeographicNode, Spot
from app.services.url_mapping import URLMappingService

bp = Blueprint("geography", __name__, url_prefix="/loc")


def get_descendant_node_ids(node_id):
    """Get all descendant node IDs using a recursive CTE for better performance"""

    # Use a Common Table Expression (CTE) to efficiently get all descendants
    cte_query = text(
        """
        WITH RECURSIVE descendants AS (
            -- Base case: the node itself
            SELECT id, parent_id, admin_level
            FROM geographic_node
            WHERE id = :node_id

            UNION ALL

            -- Recursive case: all children of nodes in the result set
            SELECT gn.id, gn.parent_id, gn.admin_level
            FROM geographic_node gn
            INNER JOIN descendants d ON gn.parent_id = d.id
        )
        SELECT id FROM descendants
    """
    )

    result = db.session.execute(cte_query, {"node_id": node_id})
    return [row[0] for row in result]


@bp.route("/<path:geographic_path>")
@cache.cached(query_string=True)
def get_geographic_area(geographic_path):
    """Handle geographic paths like /loc/us/ca/san-diego"""

    # Split the path into segments
    path_segments = geographic_path.strip("/").split("/")

    # Find the geographic node for this path
    node = URLMappingService.find_node_by_path(path_segments)

    if not node:
        # Check if this might be a spot URL (ends with name-id pattern)
        if len(path_segments) > 0:
            last_segment = path_segments[-1]
            # Check if last segment matches spot pattern (name-id)
            spot_match = re.match(r"^(.+)-(\d+)$", last_segment)
            if spot_match:
                spot_name, spot_id = spot_match.groups()
                return get_spot_by_geographic_path(path_segments[:-1], int(spot_id))

        abort(404, description="Geographic area not found")

    # Get descendant node IDs efficiently using CTE
    descendant_node_ids = get_descendant_node_ids(node.id)

    # Get content type from query params
    content_type = request.args.get("type", "spots")
    if content_type not in ["spots", "shops", "all"]:
        content_type = "spots"

    # Get limit and offset for pagination
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Get sort parameter
    sort = request.args.get("sort", "top")

    response_data = {
        "area": node.get_dict(),
        "content_type": content_type,
        "pagination": {"limit": limit, "offset": offset},
    }

    # Get spots if requested
    if content_type in ["spots", "all"]:
        spots_query = Spot.query.filter(Spot.geographic_node_id.in_(descendant_node_ids))
        spots_query = spots_query.filter(Spot.is_verified.isnot(False))
        spots_query = spots_query.filter(Spot.is_deleted.isnot(True))

        # Apply sorting at database level
        if sort == "top":
            # For now, use a simple sort by reviews and rating
            # We'll apply the confidence score sorting in Python to avoid PostgreSQL issues
            spots_query = spots_query.order_by(
                func.coalesce(Spot.num_reviews, 0).desc(),
                func.cast(Spot.rating, db.Float).desc().nullslast(),
            )
        elif sort == "latest":
            spots_query = spots_query.order_by(Spot.last_review_date.desc().nullslast())
        elif sort == "most_reviewed":
            spots_query = spots_query.order_by(Spot.num_reviews.desc().nullslast())
        else:
            spots_query = spots_query.order_by(Spot.num_reviews.desc().nullslast())

        # Get total count for pagination
        total_spots = spots_query.count()

        # Apply pagination
        spots_query = spots_query.offset(offset).limit(limit)

        # Eager load relationships to avoid N+1 queries
        spots_query = spots_query.options(
            joinedload(Spot.geographic_node),
            joinedload(Spot.reviews),
            joinedload(Spot.images),
        )

        spots = spots_query.all()

        # Apply confidence score sorting in Python if needed
        if sort == "top":
            spots.sort(key=lambda spot: spot.get_confidence_score(), reverse=True)

        response_data["spots"] = [spot.get_dict() for spot in spots]
        response_data["total_spots"] = total_spots
        response_data["pagination"]["total"] = total_spots

    # Get dive shops if requested
    if content_type in ["shops", "all"]:
        shops_query = DiveShop.query.filter(DiveShop.geographic_node_id.in_(descendant_node_ids))

        # Apply sorting at database level
        if sort == "top":
            shops_query = shops_query.order_by(
                func.coalesce(DiveShop.rating, 0).desc(),
                func.coalesce(DiveShop.num_reviews, 0).desc(),
            )
        elif sort == "latest":
            shops_query = shops_query.order_by(DiveShop.created.desc())
        elif sort == "most_reviewed":
            shops_query = shops_query.order_by(DiveShop.num_reviews.desc().nullslast())
        else:
            shops_query = shops_query.order_by(DiveShop.rating.desc().nullslast())

        # Get total count for pagination
        total_shops = shops_query.count()

        # Apply pagination
        shops_query = shops_query.offset(offset).limit(limit)

        # Eager load relationships
        shops_query = shops_query.options(joinedload(DiveShop.geographic_node), joinedload(DiveShop.reviews))

        dive_shops = shops_query.all()

        response_data["dive_shops"] = [shop.get_dict() for shop in dive_shops]
        response_data["total_shops"] = total_shops
        response_data["pagination"]["total"] = total_shops

    return response_data


@bp.route("/<path:geographic_path>/<int:spot_id>")
@cache.cached()
def get_spot_by_geographic_path(geographic_path, spot_id):
    """Handle spot URLs like /loc/us/ca/san-diego/la-jolla-cove-123"""

    # Find the spot with eager loading
    spot = (
        Spot.query.options(
            joinedload(Spot.geographic_node),
            joinedload(Spot.reviews),
            joinedload(Spot.images),
            joinedload(Spot.tags),
        )
        .filter_by(id=spot_id)
        .first_or_404()
    )

    # Verify the geographic path matches the spot's location
    if spot.geographic_node:
        expected_path = "/".join([node.short_name for node in spot.geographic_node.get_path_to_root()])
        if expected_path != geographic_path:
            abort(404, description="Spot not found at this location")

    # Format response
    spot_data = spot.get_dict()

    # Add geographic context
    if spot.geographic_node:
        spot_data["geographic_node"] = spot.geographic_node.get_dict()

    return {"data": spot_data}


@bp.route("/<path:geographic_path>/<spot_name_id>")
@cache.cached()
def get_spot_by_name_id(geographic_path, spot_name_id):
    """Handle spot URLs like /loc/us/ca/san-diego/la-jolla-cove-123"""

    # Extract spot ID from the name-id pattern
    spot_match = re.match(r"^(.+)-(\d+)$", spot_name_id)
    if not spot_match:
        # If this doesn't match the spot pattern, it might be a geographic path
        # Try to find it as a geographic node instead
        path_segments = (geographic_path + "/" + spot_name_id).strip("/").split("/")
        node = URLMappingService.find_node_by_path(path_segments)
        if node:
            # This is actually a geographic path, redirect to the geographic area handler
            return get_geographic_area(geographic_path + "/" + spot_name_id)
        abort(404, description="Invalid spot URL format")

    spot_name, spot_id = spot_match.groups()
    return get_spot_by_geographic_path(geographic_path, int(spot_id))


@bp.route("/<path:geographic_path>/stats")
@cache.cached()
def get_geographic_stats(geographic_path):
    """Get statistics for a geographic area"""

    # Split the path into segments
    path_segments = geographic_path.strip("/").split("/")

    # Find the geographic node for this path
    node = URLMappingService.find_node_by_path(path_segments)

    if not node:
        abort(404, description="Geographic area not found")

    # Get descendant node IDs efficiently
    descendant_node_ids = get_descendant_node_ids(node.id)

    # Get counts using efficient queries
    spots_count = Spot.query.filter(
        Spot.geographic_node_id.in_(descendant_node_ids),
        Spot.is_verified.isnot(False),
        Spot.is_deleted.isnot(True),
    ).count()

    shops_count = DiveShop.query.filter(DiveShop.geographic_node_id.in_(descendant_node_ids)).count()

    # Get child geographic nodes
    child_nodes = GeographicNode.query.filter_by(parent_id=node.id).all()

    return {
        "area": node.get_dict(),
        "stats": {
            "total_spots": spots_count,
            "total_shops": shops_count,
            "child_areas": len(child_nodes),
        },
        "child_areas": [child.get_simple_dict() for child in child_nodes],
    }
