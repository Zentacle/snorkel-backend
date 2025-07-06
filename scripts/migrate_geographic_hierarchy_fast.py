#!/usr/bin/env python3
"""
Fast migration script to create geographic nodes from existing hierarchy
Uses batch operations and bulk inserts for performance
Handles duplicate data gracefully by merging nodes
"""

import os
import sys
from collections import defaultdict

from sqlalchemy import func

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import AreaOne, AreaTwo, Country, GeographicNode, Locality, Spot


def migrate_existing_hierarchy_fast():
    """Migrate existing geographic hierarchy to new system using batch operations"""

    app = create_app()
    with app.app_context():

        print("Starting fast geographic hierarchy migration...")

        # Step 1: Create all nodes in batches
        print("Creating geographic nodes in batches...")

        # Create countries batch
        print("Creating countries...")
        countries = Country.query.all()
        country_nodes = []
        for country in countries:
            country_nodes.append({
                'name': country.name,
                'short_name': country.short_name,
                'admin_level': 0,
                'legacy_country_id': country.id,
                'description': country.description,
                'map_image_url': country.map_image_url
            })

        db.session.bulk_insert_mappings(GeographicNode, country_nodes)
        db.session.commit()
        print(f"Created {len(country_nodes)} country nodes")

        # Create area_ones batch
        print("Creating area_ones...")
        area_ones = AreaOne.query.all()
        area_one_nodes = []
        for area_one in area_ones:
            area_one_nodes.append({
                'name': area_one.name,
                'short_name': area_one.short_name,
                'google_name': area_one.google_name,
                'admin_level': 1,
                'legacy_country_id': area_one.country_id,
                'legacy_area_one_id': area_one.id,
                'description': area_one.description,
                'map_image_url': area_one.map_image_url
            })

        db.session.bulk_insert_mappings(GeographicNode, area_one_nodes)
        db.session.commit()
        print(f"Created {len(area_one_nodes)} area_one nodes")

        # Create area_twos batch
        print("Creating area_twos...")
        area_twos = AreaTwo.query.all()
        area_two_nodes = []
        for area_two in area_twos:
            area_two_nodes.append({
                'name': area_two.name,
                'short_name': area_two.short_name,
                'google_name': area_two.google_name,
                'admin_level': 2,
                'legacy_country_id': area_two.country_id,
                'legacy_area_one_id': area_two.area_one_id,
                'legacy_area_two_id': area_two.id,
                'description': area_two.description,
                'map_image_url': area_two.map_image_url
            })

        db.session.bulk_insert_mappings(GeographicNode, area_two_nodes)
        db.session.commit()
        print(f"Created {len(area_two_nodes)} area_two nodes")

        # Create localities batch
        print("Creating localities...")
        localities = Locality.query.all()
        locality_nodes = []
        for locality in localities:
            locality_nodes.append({
                'name': locality.name,
                'short_name': locality.short_name,
                'google_name': locality.google_name,
                'admin_level': 3,
                'legacy_country_id': locality.country_id,
                'legacy_area_one_id': locality.area_one_id,
                'legacy_area_two_id': locality.area_two_id,
                'legacy_locality_id': locality.id,
                'description': locality.description,
                'map_image_url': locality.map_image_url
            })

        db.session.bulk_insert_mappings(GeographicNode, locality_nodes)
        db.session.commit()
        print(f"Created {len(locality_nodes)} locality nodes")

        # Step 2: Create additional nodes from existing data
        print("Creating additional geographic nodes...")

        # Create nodes for unique combinations that don't exist yet
        additional_nodes = create_additional_nodes()

        if additional_nodes:
            db.session.bulk_insert_mappings(GeographicNode, additional_nodes)
            db.session.commit()
            print(f"Created {len(additional_nodes)} additional nodes")

        print("All geographic nodes created!")

        # Step 3: Merge duplicate nodes before setting relationships
        print("Merging duplicate nodes...")
        merge_duplicate_nodes()

def create_additional_nodes():
    """Create additional geographic nodes from existing data"""

    additional_nodes = []

    # Get all unique combinations from spots that don't have corresponding nodes
    spots = db.session.query(
        Spot.country_id,
        Spot.area_one_id,
        Spot.area_two_id,
        Spot.locality_id
    ).filter(
        Spot.country_id.isnot(None)
    ).distinct().all()

    existing_combinations = set()

    # Get existing combinations from geographic nodes
    existing_nodes = GeographicNode.query.all()
    for node in existing_nodes:
        combination = (
            node.legacy_country_id,
            node.legacy_area_one_id,
            node.legacy_area_two_id,
            node.legacy_locality_id
        )
        existing_combinations.add(combination)

    # Create nodes for missing combinations
    for spot in spots:
        combination = (spot.country_id, spot.area_one_id, spot.area_two_id, spot.locality_id)

        if combination not in existing_combinations:
            # Determine the appropriate level and name
            node_data = create_node_from_combination(combination)
            if node_data:
                additional_nodes.append(node_data)
                existing_combinations.add(combination)

    return additional_nodes

def create_node_from_combination(combination):
    """Create a node from a combination of legacy IDs"""

    country_id, area_one_id, area_two_id, locality_id = combination

    # If we have a locality, we already have a node for this
    if locality_id:
        return None

    # If we have area_two but no locality, create a node for the area_two
    if area_two_id and not locality_id:
        area_two = AreaTwo.query.get(area_two_id)
        if area_two:
            return {
                'name': area_two.name,
                'short_name': area_two.short_name,
                'google_name': area_two.google_name,
                'admin_level': 2,
                'legacy_country_id': country_id,
                'legacy_area_one_id': area_one_id,
                'legacy_area_two_id': area_two_id,
                'description': area_two.description,
                'map_image_url': area_two.map_image_url
            }

    # If we have area_one but no area_two, create a node for the area_one
    if area_one_id and not area_two_id:
        area_one = AreaOne.query.get(area_one_id)
        if area_one:
            return {
                'name': area_one.name,
                'short_name': area_one.short_name,
                'google_name': area_one.google_name,
                'admin_level': 1,
                'legacy_country_id': country_id,
                'legacy_area_one_id': area_one_id,
                'description': area_one.description,
                'map_image_url': area_one.map_image_url
            }

    return None

def merge_duplicate_nodes():
    """Merge duplicate geographic nodes to prevent constraint violations"""

    print("Detecting and merging duplicate nodes...")

    # Find duplicates by (admin_level, short_name) combination
    duplicates = find_duplicate_nodes()

    if not duplicates:
        print("No duplicate nodes found.")
        return

    print(f"Found {len(duplicates)} groups of duplicate nodes to merge")

    total_merged = 0
    for duplicate_group in duplicates:
        merged_count = merge_duplicate_group(duplicate_group)
        total_merged += merged_count

    print(f"Successfully merged {total_merged} duplicate nodes")

def find_duplicate_nodes():
    """Find groups of duplicate nodes that would cause constraint violations"""

    # Find duplicates that would violate the unique constraint (parent_id, short_name)
    # We need to find nodes with the same short_name that would end up with the same parent_id

    duplicate_groups = []

    # Get all nodes grouped by short_name
    short_name_groups = db.session.query(
        GeographicNode.short_name,
        func.count(GeographicNode.id).label('count')
    ).group_by(GeographicNode.short_name).having(
        func.count(GeographicNode.id) > 1
    ).all()

    for short_name, count in short_name_groups:
        # Get all nodes with this short_name
        nodes = GeographicNode.query.filter_by(short_name=short_name).order_by(GeographicNode.id).all()

        # Group by their potential parent context (legacy hierarchy)
        parent_contexts = {}
        for node in nodes:
            # Create a key based on the legacy hierarchy that would determine the parent
            if node.admin_level == 0:  # Country - no parent
                context_key = "root"
            elif node.admin_level == 1:  # AreaOne - parent is country
                context_key = f"country_{node.legacy_country_id}"
            elif node.admin_level == 2:  # AreaTwo - parent is area_one
                context_key = f"area_one_{node.legacy_area_one_id}"
            elif node.admin_level == 3:  # Locality - parent is area_two
                context_key = f"area_two_{node.legacy_area_two_id}"
            else:
                context_key = "unknown"

            if context_key not in parent_contexts:
                parent_contexts[context_key] = []
            parent_contexts[context_key].append(node)

        # Check if any context has multiple nodes (these would be real duplicates)
        for context_key, context_nodes in parent_contexts.items():
            if len(context_nodes) > 1:
                duplicate_groups.append(context_nodes)
                print(f"  Found {len(context_nodes)} duplicates for short_name='{short_name}' in context '{context_key}'")

    return duplicate_groups

def merge_duplicate_group(duplicate_nodes):
    """Merge a group of duplicate nodes into one"""

    if len(duplicate_nodes) <= 1:
        return 0

    # Keep the first node (lowest ID) as the primary node
    primary_node = duplicate_nodes[0]
    nodes_to_merge = duplicate_nodes[1:]

    print(f"  Merging {len(nodes_to_merge)} duplicates into node ID {primary_node.id} ({primary_node.name})")

    # Merge legacy IDs from all duplicate nodes into the primary node
    for node in nodes_to_merge:
        # Merge legacy IDs if they're not already set in primary
        if node.legacy_country_id and not primary_node.legacy_country_id:
            primary_node.legacy_country_id = node.legacy_country_id
        if node.legacy_area_one_id and not primary_node.legacy_area_one_id:
            primary_node.legacy_area_one_id = node.legacy_area_one_id
        if node.legacy_area_two_id and not primary_node.legacy_area_two_id:
            primary_node.legacy_area_two_id = node.legacy_area_two_id
        if node.legacy_locality_id and not primary_node.legacy_locality_id:
            primary_node.legacy_locality_id = node.legacy_locality_id

        # Merge other fields if they're not set in primary
        if node.google_name and not primary_node.google_name:
            primary_node.google_name = node.google_name
        if node.description and not primary_node.description:
            primary_node.description = node.description
        if node.map_image_url and not primary_node.map_image_url:
            primary_node.map_image_url = node.map_image_url
        if node.latitude and not primary_node.latitude:
            primary_node.latitude = node.latitude
        if node.longitude and not primary_node.longitude:
            primary_node.longitude = node.longitude
        if node.country_code and not primary_node.country_code:
            primary_node.country_code = node.country_code

    # Delete the duplicate nodes
    for node in nodes_to_merge:
        db.session.delete(node)

    # Commit the changes
    db.session.commit()

    return len(nodes_to_merge)

def handle_potential_duplicates(updates, admin_level):
    """Handle potential duplicates before setting parent relationships"""

    print(f"  Checking for potential duplicates in admin_level {admin_level} updates...")

    # Group updates by parent_id and short_name
    parent_short_name_groups = {}
    for node_id, parent_id in updates:
        # Get the node to find its short_name
        node = GeographicNode.query.get(node_id)
        if node:
            key = (parent_id, node.short_name)
            if key not in parent_short_name_groups:
                parent_short_name_groups[key] = []
            parent_short_name_groups[key].append(node_id)

    # Find groups with multiple nodes (potential duplicates)
    safe_updates = []
    duplicates_found = 0

    for (parent_id, short_name), node_ids in parent_short_name_groups.items():
        if len(node_ids) > 1:
            # We have duplicates - merge them
            print(f"    Found {len(node_ids)} duplicates for parent_id={parent_id}, short_name='{short_name}'")
            duplicates_found += len(node_ids) - 1

            # Keep the first node, merge others into it
            primary_node_id = node_ids[0]
            nodes_to_merge = node_ids[1:]

            # Merge the duplicate nodes
            merge_duplicate_nodes_by_ids(primary_node_id, nodes_to_merge)

            # Only add the primary node to safe updates
            safe_updates.append((primary_node_id, parent_id))
        else:
            # No duplicates, safe to proceed
            safe_updates.append((node_ids[0], parent_id))

    if duplicates_found > 0:
        print(f"    Merged {duplicates_found} duplicate nodes during parent relationship setup")

    return safe_updates

def merge_duplicate_nodes_by_ids(primary_node_id, duplicate_node_ids):
    """Merge duplicate nodes by their IDs"""

    primary_node = GeographicNode.query.get(primary_node_id)
    if not primary_node:
        return

    for duplicate_id in duplicate_node_ids:
        duplicate_node = GeographicNode.query.get(duplicate_id)
        if not duplicate_node:
            continue

        # Merge legacy IDs from duplicate into primary
        if duplicate_node.legacy_country_id and not primary_node.legacy_country_id:
            primary_node.legacy_country_id = duplicate_node.legacy_country_id
        if duplicate_node.legacy_area_one_id and not primary_node.legacy_area_one_id:
            primary_node.legacy_area_one_id = duplicate_node.legacy_area_one_id
        if duplicate_node.legacy_area_two_id and not primary_node.legacy_area_two_id:
            primary_node.legacy_area_two_id = duplicate_node.legacy_area_two_id
        if duplicate_node.legacy_locality_id and not primary_node.legacy_locality_id:
            primary_node.legacy_locality_id = duplicate_node.legacy_locality_id

        # Merge other fields if they're not set in primary
        if duplicate_node.google_name and not primary_node.google_name:
            primary_node.google_name = duplicate_node.google_name
        if duplicate_node.description and not primary_node.description:
            primary_node.description = duplicate_node.description
        if duplicate_node.map_image_url and not primary_node.map_image_url:
            primary_node.map_image_url = duplicate_node.map_image_url
        if duplicate_node.latitude and not primary_node.latitude:
            primary_node.latitude = duplicate_node.latitude
        if duplicate_node.longitude and not primary_node.longitude:
            primary_node.longitude = duplicate_node.longitude
        if duplicate_node.country_code and not primary_node.country_code:
            primary_node.country_code = duplicate_node.country_code

        # Delete the duplicate node
        db.session.delete(duplicate_node)

    db.session.commit()

def build_hierarchy_relationships_fast():
    """Build parent-child relationships between geographic nodes using efficient queries"""

    app = create_app()
    with app.app_context():

        print("Building hierarchy relationships efficiently...")

        # Step 1: Set parent relationships for all nodes
        print("Setting parent relationships...")

        # Build country -> area_one relationships
        print("Setting area_one parents...")
        area_ones = GeographicNode.query.filter_by(admin_level=1).all()
        area_one_updates = []

        for area_one in area_ones:
            if area_one.legacy_country_id:
                country_node = GeographicNode.query.filter_by(
                    legacy_country_id=area_one.legacy_country_id,
                    admin_level=0
                ).first()
                if country_node:
                    area_one_updates.append((area_one.id, country_node.id))

        # Bulk update area_ones
        for area_one_id, parent_id in area_one_updates:
            db.session.execute(
                "UPDATE geographic_node SET parent_id = :parent_id WHERE id = :area_one_id",
                {'parent_id': parent_id, 'area_one_id': area_one_id}
            )
        db.session.commit()
        print(f"Set {len(area_one_updates)} area_one parent relationships")

                # Build area_one -> area_two relationships
        print("Setting area_two parents...")
        area_twos = GeographicNode.query.filter_by(admin_level=2).all()
        area_two_updates = []

        for area_two in area_twos:
            if area_two.legacy_area_one_id:
                area_one_node = GeographicNode.query.filter_by(
                    legacy_area_one_id=area_two.legacy_area_one_id,
                    admin_level=1
                ).first()
                if area_one_node:
                    area_two_updates.append((area_two.id, area_one_node.id))

        # Handle potential duplicates before bulk update
        print("Checking for potential duplicates in area_two updates...")
        safe_updates = handle_potential_duplicates(area_two_updates, 2)

        # Bulk update area_twos
        for area_two_id, parent_id in safe_updates:
            db.session.execute(
                "UPDATE geographic_node SET parent_id = :parent_id WHERE id = :area_two_id",
                {'parent_id': parent_id, 'area_two_id': area_two_id}
            )
        db.session.commit()
        print(f"Set {len(safe_updates)} area_two parent relationships")

        # Build area_two -> locality relationships
        print("Setting locality parents...")
        localities = GeographicNode.query.filter_by(admin_level=3).all()
        locality_updates = []

        for locality in localities:
            if locality.legacy_area_two_id:
                area_two_node = GeographicNode.query.filter_by(
                    legacy_area_two_id=locality.legacy_area_two_id,
                    admin_level=2
                ).first()
                if area_two_node:
                    locality_updates.append((locality.id, area_two_node.id))

        # Handle potential duplicates before bulk update
        print("Checking for potential duplicates in locality updates...")
        safe_locality_updates = handle_potential_duplicates(locality_updates, 3)

        # Bulk update localities
        for locality_id, parent_id in safe_locality_updates:
            db.session.execute(
                "UPDATE geographic_node SET parent_id = :parent_id WHERE id = :locality_id",
                {'parent_id': parent_id, 'locality_id': locality_id}
            )
        db.session.commit()
        print(f"Set {len(safe_locality_updates)} locality parent relationships")

        # Step 2: Fix parent relationships for deeper nodes
        print("Fixing parent relationships for deeper nodes...")

        # Get all nodes that don't have proper parent relationships
        nodes_without_parents = GeographicNode.query.filter(
            GeographicNode.parent_id.is_(None)
        ).filter(
            GeographicNode.admin_level > 0  # Exclude countries
        ).all()

        print(f"Found {len(nodes_without_parents)} nodes without proper parent relationships")

        # Fix parent relationships for deeper nodes
        fixed_count = 0
        for node in nodes_without_parents:
            parent_node = find_parent_node(node)
            if parent_node:
                node.parent_id = parent_node.id
                fixed_count += 1

                # Set admin_level if not set
                if node.admin_level is None:
                    node.admin_level = parent_node.admin_level + 1

                if fixed_count % 100 == 0:
                    db.session.commit()
                    print(f"  Fixed {fixed_count} parent relationships...")

        db.session.commit()
        print(f"Fixed {fixed_count} parent relationships for deeper nodes")

        # Step 3: Set root relationships efficiently
        print("Setting root relationships...")

        # For countries, root is themselves
        print("Setting country roots...")
        countries = GeographicNode.query.filter_by(admin_level=0).all()
        for country in countries:
            country.root_id = country.id
        db.session.commit()
        print(f"Set {len(countries)} country root relationships")

        # For all other nodes, find their root by traversing up the hierarchy
        print("Setting root relationships for all other nodes...")
        non_country_nodes = GeographicNode.query.filter(GeographicNode.admin_level > 0).all()

        for node in non_country_nodes:
            root_node = find_root_node(node)
            if root_node:
                node.root_id = root_node.id

        db.session.commit()
        print(f"Set root relationships for {len(non_country_nodes)} nodes")

        print("Hierarchy relationships built!")

        # Final summary
        total_nodes = GeographicNode.query.count()
        nodes_with_parents = GeographicNode.query.filter(GeographicNode.parent_id.isnot(None)).count()
        nodes_with_roots = GeographicNode.query.filter(GeographicNode.root_id.isnot(None)).count()

        print(f"\nMigration Summary:")
        print(f"  Total nodes: {total_nodes}")
        print(f"  Nodes with parents: {nodes_with_parents}")
        print(f"  Nodes with roots: {nodes_with_roots}")

def find_parent_node(node):
    """Find the appropriate parent node for a given node"""

    # If node has legacy_area_two_id, find the area_two node
    if node.legacy_area_two_id:
        parent = GeographicNode.query.filter_by(
            legacy_area_two_id=node.legacy_area_two_id,
            admin_level=2
        ).first()
        if parent:
            return parent

    # If node has legacy_area_one_id, find the area_one node
    if node.legacy_area_one_id:
        parent = GeographicNode.query.filter_by(
            legacy_area_one_id=node.legacy_area_one_id,
            admin_level=1
        ).first()
        if parent:
            return parent

    # If node has legacy_country_id, find the country node
    if node.legacy_country_id:
        parent = GeographicNode.query.filter_by(
            legacy_country_id=node.legacy_country_id,
            admin_level=0
        ).first()
        if parent:
            return parent

    return None

def find_root_node(node):
    """Find the root node by traversing up the hierarchy"""

    current = node
    visited = set()  # Prevent infinite loops

    while current and current.id not in visited:
        visited.add(current.id)

        # If this is a country, it's the root
        if current.admin_level == 0:
            return current

        # If this node has a parent, move up
        if current.parent_id:
            current = GeographicNode.query.get(current.parent_id)
        else:
            # If no parent but has legacy_country_id, find the country
            if current.legacy_country_id:
                country = GeographicNode.query.filter_by(
                    legacy_country_id=current.legacy_country_id,
                    admin_level=0
                ).first()
                if country:
                    return country
            break

    return None

if __name__ == "__main__":
    migrate_existing_hierarchy_fast()
    build_hierarchy_relationships_fast()