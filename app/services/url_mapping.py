from app import db
from app.models import GeographicNode


class URLMappingService:
    """Service to handle URL mapping between old and new geographic systems"""

    @staticmethod
    def find_node_by_legacy_path(
        country_short_name,
        area_one_short_name=None,
        area_two_short_name=None,
        locality_short_name=None,
    ):
        """Find a geographic node by legacy path components with hierarchical context"""

        # Build the query based on what components are provided
        query = GeographicNode.query

        if locality_short_name:
            # Full path: country/area_one/area_two/locality
            query = query.filter(
                GeographicNode.legacy_country.has(short_name=country_short_name),
                GeographicNode.legacy_area_one.has(short_name=area_one_short_name),
                GeographicNode.legacy_area_two.has(short_name=area_two_short_name),
                GeographicNode.legacy_locality.has(short_name=locality_short_name),
                GeographicNode.admin_level == 3,  # Locality level
            )
        elif area_two_short_name:
            # Path: country/area_one/area_two
            query = query.filter(
                GeographicNode.legacy_country.has(short_name=country_short_name),
                GeographicNode.legacy_area_one.has(short_name=area_one_short_name),
                GeographicNode.legacy_area_two.has(short_name=area_two_short_name),
                GeographicNode.admin_level == 2,  # Area two level
            )
        elif area_one_short_name:
            # Path: country/area_one
            query = query.filter(
                GeographicNode.legacy_country.has(short_name=country_short_name),
                GeographicNode.legacy_area_one.has(short_name=area_one_short_name),
                GeographicNode.admin_level == 1,  # Area one level
            )
        else:
            # Path: country
            query = query.filter(
                GeographicNode.legacy_country.has(short_name=country_short_name),
                GeographicNode.admin_level == 0,  # Country level
            )

        return query.first()

    @staticmethod
    def create_legacy_mapping(country, area_one=None, area_two=None, locality=None):
        """Create a mapping between legacy entities and new geographic node"""

        # Find or create the appropriate geographic node
        if locality:
            # This is the most specific level
            node = GeographicNode.query.filter_by(legacy_locality_id=locality.id).first()

            if not node:
                node = GeographicNode(
                    name=locality.name,
                    short_name=locality.short_name,
                    google_name=locality.google_name,
                    admin_level=3,  # City level
                    legacy_country_id=country.id,
                    legacy_area_one_id=area_one.id if area_one else None,
                    legacy_area_two_id=area_two.id if area_two else None,
                    legacy_locality_id=locality.id,
                    description=locality.description,
                    map_image_url=locality.map_image_url,
                )
                db.session.add(node)

        elif area_two:
            node = GeographicNode.query.filter_by(legacy_area_two_id=area_two.id).first()

            if not node:
                node = GeographicNode(
                    name=area_two.name,
                    short_name=area_two.short_name,
                    google_name=area_two.google_name,
                    admin_level=2,  # County level
                    legacy_country_id=country.id,
                    legacy_area_one_id=area_one.id if area_one else None,
                    legacy_area_two_id=area_two.id,
                    description=area_two.description,
                    map_image_url=area_two.map_image_url,
                )
                db.session.add(node)

        elif area_one:
            node = GeographicNode.query.filter_by(legacy_area_one_id=area_one.id).first()

            if not node:
                node = GeographicNode(
                    name=area_one.name,
                    short_name=area_one.short_name,
                    google_name=area_one.google_name,
                    admin_level=1,  # State level
                    legacy_country_id=country.id,
                    legacy_area_one_id=area_one.id,
                    description=area_one.description,
                    map_image_url=area_one.map_image_url,
                )
                db.session.add(node)

        else:
            node = GeographicNode.query.filter_by(legacy_country_id=country.id).first()

            if not node:
                node = GeographicNode(
                    name=country.name,
                    short_name=country.short_name,
                    admin_level=0,  # Country level
                    legacy_country_id=country.id,
                    description=country.description,
                    map_image_url=country.map_image_url,
                )
                db.session.add(node)

        db.session.commit()
        return node

    @staticmethod
    def find_node_by_path(path_segments):
        """Find a geographic node by its path segments with hierarchical context"""
        if not path_segments:
            return None

        # Start with the first segment (country level)
        current_node = GeographicNode.query.filter_by(
            short_name=path_segments[0],
            admin_level=0,  # Country level
            parent_id=None,  # Root level
        ).first()

        if not current_node:
            return None

        # Traverse down the path, using parent context for each level
        for i, segment in enumerate(path_segments[1:], 1):
            child = GeographicNode.query.filter_by(
                short_name=segment,
                parent_id=current_node.id,
                admin_level=i,  # Ensure correct admin level
            ).first()

            if not child:
                return None

            current_node = child

        return current_node
