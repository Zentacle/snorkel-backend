#!/usr/bin/env python3
"""
Test script to test the full migration process with just a few items
"""

import sys
import os

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Country, AreaOne, AreaTwo, Locality, GeographicNode

def test_full_migration():
    """Test the full migration process with just a few items"""

    app = create_app()
    with app.app_context():

        print("Starting test full migration...")

        # Create a mapping to store created nodes
        created_nodes = {}

        # Get just a few items for testing
        test_country = Country.query.first()
        if not test_country:
            print("No countries found!")
            return

        print(f"Testing with country: {test_country.name}")

        test_area_one = AreaOne.query.filter_by(country_id=test_country.id).first()
        if not test_area_one:
            print("No area_ones found for this country!")
            return

        print(f"Testing with area_one: {test_area_one.name}")

        test_area_two = AreaTwo.query.filter_by(country_id=test_country.id, area_one_id=test_area_one.id).first()
        if not test_area_two:
            print("No area_twos found for this area_one!")
            return

        print(f"Testing with area_two: {test_area_two.name}")

        test_locality = Locality.query.filter_by(country_id=test_country.id, area_one_id=test_area_one.id, area_two_id=test_area_two.id).first()
        if not test_locality:
            print("No localities found for this area_two!")
            return

        print(f"Testing with locality: {test_locality.name}")

        # Create geographic nodes manually (like the updated migration script)
        print("\nCreating geographic nodes...")

        # Create country node
        country_node = GeographicNode(
            name=test_country.name,
            short_name=test_country.short_name,
            admin_level=0,
            legacy_country_id=test_country.id,
            description=test_country.description,
            map_image_url=test_country.map_image_url
        )
        db.session.add(country_node)
        db.session.commit()
        created_nodes[f"country_{test_country.id}"] = country_node
        print(f"Created country node: {country_node.name} (ID: {country_node.id})")

        # Create area_one node
        area_one_node = GeographicNode(
            name=test_area_one.name,
            short_name=test_area_one.short_name,
            google_name=test_area_one.google_name,
            admin_level=1,
            legacy_country_id=test_area_one.country_id,
            legacy_area_one_id=test_area_one.id,
            description=test_area_one.description,
            map_image_url=test_area_one.map_image_url
        )
        db.session.add(area_one_node)
        db.session.commit()
        created_nodes[f"area_one_{test_area_one.id}"] = area_one_node
        print(f"Created area_one node: {area_one_node.name} (ID: {area_one_node.id})")

        # Create area_two node
        area_two_node = GeographicNode(
            name=test_area_two.name,
            short_name=test_area_two.short_name,
            google_name=test_area_two.google_name,
            admin_level=2,
            legacy_country_id=test_area_two.country_id,
            legacy_area_one_id=test_area_two.area_one_id,
            legacy_area_two_id=test_area_two.id,
            description=test_area_two.description,
            map_image_url=test_area_two.map_image_url
        )
        db.session.add(area_two_node)
        db.session.commit()
        created_nodes[f"area_two_{test_area_two.id}"] = area_two_node
        print(f"Created area_two node: {area_two_node.name} (ID: {area_two_node.id})")

        # Create locality node
        locality_node = GeographicNode(
            name=test_locality.name,
            short_name=test_locality.short_name,
            google_name=test_locality.google_name,
            admin_level=3,
            legacy_country_id=test_locality.country_id,
            legacy_area_one_id=test_locality.area_one_id,
            legacy_area_two_id=test_locality.area_two_id,
            legacy_locality_id=test_locality.id,
            description=test_locality.description,
            map_image_url=test_locality.map_image_url
        )
        db.session.add(locality_node)
        db.session.commit()
        created_nodes[f"locality_{test_locality.id}"] = locality_node
        print(f"Created locality node: {locality_node.name} (ID: {locality_node.id})")

        # Now build hierarchy relationships (like the updated migration script)
        print("\nBuilding hierarchy relationships...")

        # Step 1: Set parent relationships first
        print("Setting parent relationships...")

        # Build country -> area_one relationships
        area_ones = GeographicNode.query.filter_by(admin_level=1).all()
        for area_one in area_ones:
            if area_one.legacy_country_id:
                country_node = GeographicNode.query.filter_by(
                    legacy_country_id=area_one.legacy_country_id
                ).first()
                if country_node:
                    area_one.parent_id = country_node.id
                    print(f"Set parent: {area_one.name} -> {country_node.name}")

        # Build area_one -> area_two relationships
        area_twos = GeographicNode.query.filter_by(admin_level=2).all()
        for area_two in area_twos:
            if area_two.legacy_area_one_id:
                area_one_node = GeographicNode.query.filter_by(
                    legacy_area_one_id=area_two.legacy_area_one_id,
                    admin_level=1  # Make sure we get the area_one, not the area_two
                ).first()
                if area_one_node:
                    area_two.parent_id = area_one_node.id
                    print(f"Set parent: {area_two.name} -> {area_one_node.name}")

        # Build area_two -> locality relationships
        localities = GeographicNode.query.filter_by(admin_level=3).all()
        for locality in localities:
            if locality.legacy_area_two_id:
                area_two_node = GeographicNode.query.filter_by(
                    legacy_area_two_id=locality.legacy_area_two_id,
                    admin_level=2  # Make sure we get the area_two, not the locality
                ).first()
                if area_two_node:
                    locality.parent_id = area_two_node.id
                    print(f"Set parent: {locality.name} -> {area_two_node.name}")

        # Commit parent relationships first
        db.session.commit()
        print("Parent relationships committed!")

        # Step 2: Set root relationships (using parent relationships)
        print("Setting root relationships...")

        # For countries, root is themselves
        countries = GeographicNode.query.filter_by(admin_level=0).all()
        for country in countries:
            country.root_id = country.id

        # For area_ones, root is their parent (country)
        area_ones = GeographicNode.query.filter_by(admin_level=1).all()
        for area_one in area_ones:
            if area_one.parent_id:
                area_one.root_id = area_one.parent_id

        # For area_twos, root is their grandparent (country)
        area_twos = GeographicNode.query.filter_by(admin_level=2).all()
        for area_two in area_twos:
            if area_two.parent_id:
                parent = GeographicNode.query.get(area_two.parent_id)
                if parent and parent.root_id:
                    area_two.root_id = parent.root_id

        # For localities, root is their great-grandparent (country)
        localities = GeographicNode.query.filter_by(admin_level=3).all()
        for locality in localities:
            if locality.parent_id:
                parent = GeographicNode.query.get(locality.parent_id)
                if parent and parent.root_id:
                    locality.root_id = parent.root_id

        db.session.commit()
        print("Root relationships committed!")

        # Debug: Check final state
        print("\nFinal state:")
        for node in GeographicNode.query.all():
            parent = GeographicNode.query.get(node.parent_id) if node.parent_id else None
            root = GeographicNode.query.get(node.root_id) if node.root_id else None
            print(f"  {node.name} (level {node.admin_level}): parent={parent.name if parent else 'None'}, root={root.name if root else 'None'}")

        print("\nTest full migration completed!")

if __name__ == "__main__":
    test_full_migration()