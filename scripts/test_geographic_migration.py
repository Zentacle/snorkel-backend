#!/usr/bin/env python3
"""
Test script to populate a few geographic nodes and debug parent/root relationships
"""

import sys
import os

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Country, AreaOne, AreaTwo, Locality, GeographicNode

def test_geographic_migration():
    """Test migration with just a few items"""

    app = create_app()
    with app.app_context():

        print("Starting test geographic migration...")

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

        # Create geographic nodes manually
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
        print(f"Created country node: {country_node.name} (ID: {country_node.id})")

        # Create area_one node
        area_one_node = GeographicNode(
            name=test_area_one.name,
            short_name=test_area_one.short_name,
            google_name=test_area_one.google_name,
            admin_level=1,
            legacy_country_id=test_country.id,
            legacy_area_one_id=test_area_one.id,
            description=test_area_one.description,
            map_image_url=test_area_one.map_image_url
        )
        db.session.add(area_one_node)
        db.session.commit()
        print(f"Created area_one node: {area_one_node.name} (ID: {area_one_node.id})")

        # Create area_two node
        area_two_node = GeographicNode(
            name=test_area_two.name,
            short_name=test_area_two.short_name,
            google_name=test_area_two.google_name,
            admin_level=2,
            legacy_country_id=test_country.id,
            legacy_area_one_id=test_area_one.id,
            legacy_area_two_id=test_area_two.id,
            description=test_area_two.description,
            map_image_url=test_area_two.map_image_url
        )
        db.session.add(area_two_node)
        db.session.commit()
        print(f"Created area_two node: {area_two_node.name} (ID: {area_two_node.id})")

        # Create locality node
        locality_node = GeographicNode(
            name=test_locality.name,
            short_name=test_locality.short_name,
            google_name=test_locality.google_name,
            admin_level=3,
            legacy_country_id=test_country.id,
            legacy_area_one_id=test_area_one.id,
            legacy_area_two_id=test_area_two.id,
            legacy_locality_id=test_locality.id,
            description=test_locality.description,
            map_image_url=test_locality.map_image_url
        )
        db.session.add(locality_node)
        db.session.commit()
        print(f"Created locality node: {locality_node.name} (ID: {locality_node.id})")

        # Now set parent relationships
        print("\nSetting parent relationships...")

        # Area_one -> Country
        area_one_node.parent_id = country_node.id
        print(f"Set parent: {area_one_node.name} -> {country_node.name}")

        # Area_two -> Area_one
        area_two_node.parent_id = area_one_node.id
        print(f"Set parent: {area_two_node.name} -> {area_one_node.name}")

        # Locality -> Area_two
        locality_node.parent_id = area_two_node.id
        print(f"Set parent: {locality_node.name} -> {area_two_node.name}")

        db.session.commit()
        print("Parent relationships committed!")

        # Set root relationships
        print("\nSetting root relationships...")

        # Country root is itself
        country_node.root_id = country_node.id
        print(f"Set root: {country_node.name} -> {country_node.name}")

        # Area_one root is country
        area_one_node.root_id = country_node.id
        print(f"Set root: {area_one_node.name} -> {country_node.name}")

        # Area_two root is country
        area_two_node.root_id = country_node.id
        print(f"Set root: {area_two_node.name} -> {country_node.name}")

        # Locality root is country
        locality_node.root_id = country_node.id
        print(f"Set root: {locality_node.name} -> {country_node.name}")

        db.session.commit()
        print("Root relationships committed!")

        # Debug: Check final state
        print("\nFinal state:")
        for node in GeographicNode.query.all():
            parent = GeographicNode.query.get(node.parent_id) if node.parent_id else None
            root = GeographicNode.query.get(node.root_id) if node.root_id else None
            print(f"  {node.name} (level {node.admin_level}): parent={parent.name if parent else 'None'}, root={root.name if root else 'None'}")

        print("\nTest migration completed!")

if __name__ == "__main__":
    test_geographic_migration()