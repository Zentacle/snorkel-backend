from flask import Blueprint, request, jsonify, abort
from app.models import GeographicNode, Spot, Country, AreaOne, AreaTwo, Locality
from app.services.url_mapping import URLMappingService
from app import cache
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, func
import re

bp = Blueprint('geography', __name__, url_prefix='/loc')

@bp.route('/<path:geographic_path>')
@cache.cached(query_string=True)
def get_geographic_area(geographic_path):
    """Handle geographic paths like /loc/us/ca/san-diego"""

    # Split the path into segments
    path_segments = geographic_path.strip('/').split('/')

    # Find the geographic node for this path
    node = URLMappingService.find_node_by_path(path_segments)

    if not node:
        # Check if this might be a spot URL (ends with name-id pattern)
        if len(path_segments) > 0:
            last_segment = path_segments[-1]
            # Check if last segment matches spot pattern (name-id)
            spot_match = re.match(r'^(.+)-(\d+)$', last_segment)
            if spot_match:
                spot_name, spot_id = spot_match.groups()
                return get_spot_by_geographic_path(path_segments[:-1], int(spot_id))

        abort(404, description="Geographic area not found")

        # Get spots in this geographic area and all descendants
    descendant_nodes = [node.id] + [desc.id for desc in node.get_descendants()]
    spots = Spot.query.filter(Spot.geographic_node_id.in_(descendant_nodes)).all()

    # Format response
    area_data = node.get_dict()
    spots_data = []

    for spot in spots:
        spot_data = spot.get_dict()
        spots_data.append(spot_data)

    return {
        'area': area_data,
        'spots': spots_data,
        'total_spots': len(spots_data)
    }

@bp.route('/<path:geographic_path>/<int:spot_id>')
@cache.cached()
def get_spot_by_geographic_path(geographic_path, spot_id):
    """Handle spot URLs like /loc/us/ca/san-diego/la-jolla-cove-123"""

    # Find the spot
    spot = Spot.query.filter_by(id=spot_id).first_or_404()

    # Verify the geographic path matches the spot's location
    if spot.geographic_node:
        expected_path = '/'.join([node.short_name for node in spot.geographic_node.get_path_to_root()])
        if expected_path != geographic_path:
            abort(404, description="Spot not found at this location")

    # Format response
    spot_data = spot.get_dict()

    # Add geographic context
    if spot.geographic_node:
        spot_data['geographic_node'] = spot.geographic_node.get_dict()

    return {'data': spot_data}

@bp.route('/<path:geographic_path>/<spot_name_id>')
@cache.cached()
def get_spot_by_name_id(geographic_path, spot_name_id):
    """Handle spot URLs like /loc/us/ca/san-diego/la-jolla-cove-123"""

    # Extract spot ID from the name-id pattern
    spot_match = re.match(r'^(.+)-(\d+)$', spot_name_id)
    if not spot_match:
        abort(404, description="Invalid spot URL format")

    spot_name, spot_id = spot_match.groups()
    return get_spot_by_geographic_path(geographic_path, int(spot_id))

