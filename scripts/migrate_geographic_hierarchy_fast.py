#!/usr/bin/env python3
"""
Fast migration script to create geographic nodes from existing hierarchy
Uses batch operations and bulk inserts for performance
Prevents duplicate nodes during creation
"""

import os
import sys
import traceback
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

        # Step 1: Create all nodes in batches with duplicate prevention
        print("Creating geographic nodes in batches...")

        # Create countries individually first (so we can set root_id)
        print("Creating countries...")
        countries = Country.query.all()
        existing_short_names = set()

        for country in countries:
            if country.short_name not in existing_short_names:
                country_node = GeographicNode(
                    name=country.name,
                    short_name=country.short_name,
                    admin_level=0,
                    legacy_country_id=country.id,
                    description=country.description,
                    map_image_url=country.map_image_url,
                )
                db.session.add(country_node)
                db.session.flush()  # Get the ID without committing

                # Set root_id to itself for countries
                country_node.root_id = country_node.id
                existing_short_names.add(country.short_name)

        db.session.commit()
        print(f"Created {len(countries)} country nodes")

        # Create area_ones batch
        print("Creating area_ones...")
        area_ones = AreaOne.query.all()
        area_one_nodes = []
        existing_combinations = set()

        for area_one in area_ones:
            # Create unique key for (country_id, short_name) combination
            combination_key = (area_one.country_id, area_one.short_name)
            if combination_key not in existing_combinations:
                area_one_nodes.append(
                    {
                        "name": area_one.name,
                        "short_name": area_one.short_name,
                        "google_name": area_one.google_name,
                        "admin_level": 1,
                        "legacy_country_id": area_one.country_id,
                        "legacy_area_one_id": area_one.id,
                        "description": area_one.description,
                        "map_image_url": area_one.map_image_url,
                    }
                )
                existing_combinations.add(combination_key)

        db.session.bulk_insert_mappings(GeographicNode, area_one_nodes)
        db.session.commit()
        print(f"Created {len(area_one_nodes)} area_one nodes")

        # Create area_twos batch
        print("Creating area_twos...")
        area_twos = AreaTwo.query.all()
        area_two_nodes = []
        existing_combinations = set()

        for area_two in area_twos:
            # Create unique key for (area_one_id, short_name) combination
            combination_key = (area_two.area_one_id, area_two.short_name)
            if combination_key not in existing_combinations:
                area_two_nodes.append(
                    {
                        "name": area_two.name,
                        "short_name": area_two.short_name,
                        "google_name": area_two.google_name,
                        "admin_level": 2,
                        "legacy_country_id": area_two.country_id,
                        "legacy_area_one_id": area_two.area_one_id,
                        "legacy_area_two_id": area_two.id,
                        "description": area_two.description,
                        "map_image_url": area_two.map_image_url,
                    }
                )
                existing_combinations.add(combination_key)

        db.session.bulk_insert_mappings(GeographicNode, area_two_nodes)
        db.session.commit()
        print(f"Created {len(area_two_nodes)} area_two nodes")

        # Create localities batch
        print("Creating localities...")
        localities = Locality.query.all()
        locality_nodes = []
        existing_combinations = set()

        for locality in localities:
            # Create unique key for (area_two_id, short_name) combination
            combination_key = (locality.area_two_id, locality.short_name)
            if combination_key not in existing_combinations:
                locality_nodes.append(
                    {
                        "name": locality.name,
                        "short_name": locality.short_name,
                        "google_name": locality.google_name,
                        "admin_level": 3,
                        "legacy_country_id": locality.country_id,
                        "legacy_area_one_id": locality.area_one_id,
                        "legacy_area_two_id": locality.area_two_id,
                        "legacy_locality_id": locality.id,
                        "description": locality.description,
                        "map_image_url": locality.map_image_url,
                    }
                )
                existing_combinations.add(combination_key)

        db.session.bulk_insert_mappings(GeographicNode, locality_nodes)
        db.session.commit()
        print(f"Created {len(locality_nodes)} locality nodes")

        # Step 2: Create additional nodes from existing data
        print("Creating additional geographic nodes...")

        # Create nodes for unique combinations that don't exist yet
        additional_nodes_created = create_additional_nodes()

        if additional_nodes_created > 0:
            print(f"Created {additional_nodes_created} additional nodes")

        print("All geographic nodes created!")


def create_additional_nodes():
    """Create additional geographic nodes from existing data"""

    additional_nodes_created = 0

    # Get all unique combinations from spots that don't have corresponding nodes
    spots = (
        db.session.query(
            Spot.country_id, Spot.area_one_id, Spot.area_two_id, Spot.locality_id
        )
        .filter(Spot.country_id.isnot(None))
        .distinct()
        .all()
    )

    existing_combinations = set()

    # Get existing combinations from geographic nodes
    existing_nodes = GeographicNode.query.all()
    for node in existing_nodes:
        combination = (
            node.legacy_country_id,
            node.legacy_area_one_id,
            node.legacy_area_two_id,
            node.legacy_locality_id,
        )
        existing_combinations.add(combination)

    # Create nodes for missing combinations
    for spot in spots:
        combination = (
            spot.country_id,
            spot.area_one_id,
            spot.area_two_id,
            spot.locality_id,
        )

        if combination not in existing_combinations:
            # Determine the appropriate level and name
            node_data = create_node_from_combination(combination)
            if node_data:
                # Create node individually so we can set root_id
                node = GeographicNode(**node_data)
                db.session.add(node)
                db.session.flush()  # Get the ID without committing

                # Set root_id based on the node's level
                if node.admin_level == 0:  # Country
                    node.root_id = node.id
                elif node.admin_level == 1:  # AreaOne - find country
                    country_node = GeographicNode.query.filter_by(
                        legacy_country_id=node.legacy_country_id, admin_level=0
                    ).first()
                    if country_node:
                        node.root_id = country_node.id
                elif node.admin_level == 2:  # AreaTwo - find country
                    country_node = GeographicNode.query.filter_by(
                        legacy_country_id=node.legacy_country_id, admin_level=0
                    ).first()
                    if country_node:
                        node.root_id = country_node.id

                additional_nodes_created += 1
                existing_combinations.add(combination)

    db.session.commit()
    return additional_nodes_created


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
                "name": area_two.name,
                "short_name": area_two.short_name,
                "google_name": area_two.google_name,
                "admin_level": 2,
                "legacy_country_id": country_id,
                "legacy_area_one_id": area_one_id,
                "legacy_area_two_id": area_two_id,
                "description": area_two.description,
                "map_image_url": area_two.map_image_url,
            }

    # If we have area_one but no area_two, create a node for the area_one
    if area_one_id and not area_two_id:
        area_one = AreaOne.query.get(area_one_id)
        if area_one:
            return {
                "name": area_one.name,
                "short_name": area_one.short_name,
                "google_name": area_one.google_name,
                "admin_level": 1,
                "legacy_country_id": country_id,
                "legacy_area_one_id": area_one_id,
                "description": area_one.description,
                "map_image_url": area_one.map_image_url,
            }

    return None


def check_parent_short_name_constraint(parent_id, short_name):
    """Check if setting parent_id would violate the (parent_id, short_name) unique constraint"""
    existing = GeographicNode.query.filter_by(
        parent_id=parent_id, short_name=short_name
    ).first()
    return existing is not None


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
                    legacy_country_id=area_one.legacy_country_id, admin_level=0
                ).first()
                if country_node and not check_parent_short_name_constraint(
                    country_node.id, area_one.short_name
                ):
                    area_one_updates.append((area_one.id, country_node.id))

        # Bulk update area_ones
        for area_one_id, parent_id in area_one_updates:
            try:
                db.session.execute(
                    "UPDATE geographic_node SET parent_id = :parent_id WHERE id = :area_one_id",
                    {"parent_id": parent_id, "area_one_id": area_one_id},
                )
            except Exception as e:
                print(
                    f"\n[ERROR] Unique constraint violation for (parent_id={parent_id}, short_name={GeographicNode.query.get(area_one_id).short_name}) during area_one parent assignment!"
                )
                print("All nodes with this parent_id and short_name:")
                nodes = GeographicNode.query.filter_by(
                    parent_id=parent_id,
                    short_name=GeographicNode.query.get(area_one_id).short_name,
                ).all()
                for n in nodes:
                    print(
                        f"  id={n.id}, name={n.name}, admin_level={n.admin_level}, legacy_country_id={n.legacy_country_id}, legacy_area_one_id={n.legacy_area_one_id}"
                    )
                print("Traceback:")
                traceback.print_exc()
                raise
        db.session.commit()
        print(f"Set {len(area_one_updates)} area_one parent relationships")

        # Build area_one -> area_two relationships
        print("Setting area_two parents...")
        area_twos = GeographicNode.query.filter_by(admin_level=2).all()
        area_two_updates = []

        for area_two in area_twos:
            if area_two.legacy_area_one_id:
                area_one_node = GeographicNode.query.filter_by(
                    legacy_area_one_id=area_two.legacy_area_one_id, admin_level=1
                ).first()
                if area_one_node and not check_parent_short_name_constraint(
                    area_one_node.id, area_two.short_name
                ):
                    area_two_updates.append((area_two.id, area_one_node.id))

        # Bulk update area_twos
        for area_two_id, parent_id in area_two_updates:
            try:
                db.session.execute(
                    "UPDATE geographic_node SET parent_id = :parent_id WHERE id = :area_two_id",
                    {"parent_id": parent_id, "area_two_id": area_two_id},
                )
            except Exception as e:
                print(
                    f"\n[ERROR] Unique constraint violation for (parent_id={parent_id}, short_name={GeographicNode.query.get(area_two_id).short_name}) during area_two parent assignment!"
                )
                print("All nodes with this parent_id and short_name:")
                nodes = GeographicNode.query.filter_by(
                    parent_id=parent_id,
                    short_name=GeographicNode.query.get(area_two_id).short_name,
                ).all()
                for n in nodes:
                    print(
                        f"  id={n.id}, name={n.name}, admin_level={n.admin_level}, legacy_area_one_id={n.legacy_area_one_id}, legacy_area_two_id={n.legacy_area_two_id}"
                    )
                print("Traceback:")
                traceback.print_exc()
                raise
        db.session.commit()
        print(f"Set {len(area_two_updates)} area_two parent relationships")

        # Build area_two -> locality relationships
        print("Setting locality parents...")
        localities = GeographicNode.query.filter_by(admin_level=3).all()
        locality_updates = []

        for locality in localities:
            if locality.legacy_area_two_id:
                area_two_node = GeographicNode.query.filter_by(
                    legacy_area_two_id=locality.legacy_area_two_id, admin_level=2
                ).first()
                if area_two_node and not check_parent_short_name_constraint(
                    area_two_node.id, locality.short_name
                ):
                    locality_updates.append((locality.id, area_two_node.id))

        # Bulk update localities
        for locality_id, parent_id in locality_updates:
            try:
                db.session.execute(
                    "UPDATE geographic_node SET parent_id = :parent_id WHERE id = :locality_id",
                    {"parent_id": parent_id, "locality_id": locality_id},
                )
            except Exception as e:
                print(
                    f"\n[ERROR] Unique constraint violation for (parent_id={parent_id}, short_name={GeographicNode.query.get(locality_id).short_name}) during locality parent assignment!"
                )
                print("All nodes with this parent_id and short_name:")
                nodes = GeographicNode.query.filter_by(
                    parent_id=parent_id,
                    short_name=GeographicNode.query.get(locality_id).short_name,
                ).all()
                for n in nodes:
                    print(
                        f"  id={n.id}, name={n.name}, admin_level={n.admin_level}, legacy_area_two_id={n.legacy_area_two_id}, legacy_locality_id={n.legacy_locality_id}"
                    )
                print("Traceback:")
                traceback.print_exc()
                raise
        db.session.commit()
        print(f"Set {len(locality_updates)} locality parent relationships")

        # Step 2: Fix parent relationships for deeper nodes
        print("Fixing parent relationships for deeper nodes...")

        # Get all nodes that don't have proper parent relationships
        nodes_without_parents = (
            GeographicNode.query.filter(GeographicNode.parent_id.is_(None))
            .filter(GeographicNode.admin_level > 0)  # Exclude countries
            .all()
        )

        print(
            f"Found {len(nodes_without_parents)} nodes without proper parent relationships"
        )

        # Fix parent relationships for deeper nodes
        fixed_count = 0
        for node in nodes_without_parents:
            parent_node = find_parent_node(node)
            if parent_node and not check_parent_short_name_constraint(
                parent_node.id, node.short_name
            ):
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
        non_country_nodes = GeographicNode.query.filter(
            GeographicNode.admin_level > 0
        ).all()

        nodes_without_roots = []
        for node in non_country_nodes:
            root_node = find_root_node(node)
            if root_node:
                node.root_id = root_node.id
            else:
                nodes_without_roots.append(node)

        db.session.commit()
        print(f"Set root relationships for {len(non_country_nodes)} nodes")

        # Debug: Show nodes without roots
        if nodes_without_roots:
            print(f"\n⚠ {len(nodes_without_roots)} nodes could not find root:")
            for node in nodes_without_roots[:10]:  # Show first 10
                print(
                    f"  - {node.name} (admin_level={node.admin_level}, parent_id={node.parent_id}, legacy_country_id={node.legacy_country_id}, legacy_area_one_id={node.legacy_area_one_id}, legacy_area_two_id={node.legacy_area_two_id})"
                )
            if len(nodes_without_roots) > 10:
                print(f"  ... and {len(nodes_without_roots) - 10} more")
        else:
            print("✓ All nodes have root relationships!")

        print("Hierarchy relationships built!")

        # Final summary
        total_nodes = GeographicNode.query.count()
        nodes_with_parents = GeographicNode.query.filter(
            GeographicNode.parent_id.isnot(None)
        ).count()
        nodes_with_roots = GeographicNode.query.filter(
            GeographicNode.root_id.isnot(None)
        ).count()

        print(f"\nMigration Summary:")
        print(f"  Total nodes: {total_nodes}")
        print(f"  Nodes with parents: {nodes_with_parents}")
        print(f"  Nodes with roots: {nodes_with_roots}")


def find_parent_node(node):
    """Find the appropriate parent node for a given node"""

    # If node has legacy_area_two_id, find the area_two node
    if node.legacy_area_two_id:
        parent = GeographicNode.query.filter_by(
            legacy_area_two_id=node.legacy_area_two_id, admin_level=2
        ).first()
        if parent:
            return parent

    # If node has legacy_area_one_id, find the area_one node
    if node.legacy_area_one_id:
        parent = GeographicNode.query.filter_by(
            legacy_area_one_id=node.legacy_area_one_id, admin_level=1
        ).first()
        if parent:
            return parent

    # If node has legacy_country_id, find the country node
    if node.legacy_country_id:
        parent = GeographicNode.query.filter_by(
            legacy_country_id=node.legacy_country_id, admin_level=0
        ).first()
        if parent:
            return parent

    return None


def find_root_node(node):
    """Find the root node by traversing up the hierarchy"""

    current = node
    visited = set()  # Prevent infinite loops

    # First try: traverse up the parent_id chain
    while current and current.id not in visited:
        visited.add(current.id)

        # If this is a country, it's the root
        if current.admin_level == 0:
            return current

        # If this node has a parent, move up
        if current.parent_id:
            current = GeographicNode.query.get(current.parent_id)
        else:
            break

    # Second try: use legacy hierarchy as fallback
    if node.legacy_country_id:
        country = GeographicNode.query.filter_by(
            legacy_country_id=node.legacy_country_id, admin_level=0
        ).first()
        if country:
            return country

    # Third try: find any country node that could be the root
    # This is a last resort for truly orphaned nodes
    if node.admin_level > 0:  # Not a country itself
        # Try to find a country by looking at the node's context
        if node.legacy_area_two_id:
            # Find the area_two node and get its country
            area_two = GeographicNode.query.filter_by(
                legacy_area_two_id=node.legacy_area_two_id, admin_level=2
            ).first()
            if area_two and area_two.root_id:
                return GeographicNode.query.get(area_two.root_id)
        elif node.legacy_area_one_id:
            # Find the area_one node and get its country
            area_one = GeographicNode.query.filter_by(
                legacy_area_one_id=node.legacy_area_one_id, admin_level=1
            ).first()
            if area_one and area_one.root_id:
                return GeographicNode.query.get(area_one.root_id)

    return None


if __name__ == "__main__":
    migrate_existing_hierarchy_fast()
    build_hierarchy_relationships_fast()
