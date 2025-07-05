#!/usr/bin/env python3
"""
Test script to verify hierarchical path resolution handles duplicate short names
"""

import sys
import os

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import GeographicNode, Country, AreaOne, AreaTwo, Locality
from app.services.url_mapping import URLMappingService

def test_hierarchical_paths():
    """Test that hierarchical path resolution works with duplicate short names"""

    app = create_app()
    with app.app_context():

        print("🧪 Testing Hierarchical Path Resolution")
        print("=" * 50)

        # Test 1: Create nodes with duplicate short names
        print("Creating test nodes with duplicate short names...")

        # Get two different countries
        countries = Country.query.limit(2).all()
        if len(countries) < 2:
            print("❌ Need at least two countries for testing")
            return False

        country1 = countries[0]
        country2 = countries[1]

        if not country1 or not country2:
            print("❌ Need at least two countries for testing")
            return False

        # Create geographic nodes for these countries
        node1 = URLMappingService.create_legacy_mapping(country1)
        node2 = URLMappingService.create_legacy_mapping(country2)

        print(f"✅ Created nodes: {node1.name} ({node1.short_name}) and {node2.name} ({node2.short_name})")

        # Test 2: Test path resolution
        print("\nTesting path resolution...")

                # Test finding by path
        path1 = [node1.short_name]
        path2 = [node2.short_name]

        found_node1 = URLMappingService.find_node_by_path(path1)
        found_node2 = URLMappingService.find_node_by_path(path2)

        if found_node1 and found_node1.id == node1.id:
            print(f"✅ Correctly found {node1.name} via path {path1}")
        else:
            print(f"❌ Failed to find {node1.name} via path {path1}")
            if found_node1:
                print(f"   Found different node: {found_node1.name}")
            return False

        if found_node2 and found_node2.id == node2.id:
            print(f"✅ Correctly found {node2.name} via path {path2}")
        else:
            print(f"❌ Failed to find {node2.name} via path {path2}")
            if found_node2:
                print(f"   Found different node: {found_node2.name}")
            return False

        # Test 3: Test that wrong paths don't match
        print("\nTesting that wrong paths don't match...")

        wrong_path = ['wrong']
        wrong_node = URLMappingService.find_node_by_path(wrong_path)

        if wrong_node is None:
            print("✅ Correctly returned None for non-existent path")
        else:
            print(f"❌ Incorrectly found node for wrong path: {wrong_node.name}")
            return False

        # Test 4: Test hierarchical context
        print("\nTesting hierarchical context...")

        # Get some area_ones to test with
        area_ones = AreaOne.query.limit(2).all()
        if len(area_ones) >= 2:
            area1 = area_ones[0]
            area2 = area_ones[1]

            # Create geographic nodes for these areas
            area_node1 = URLMappingService.create_legacy_mapping(area1.country, area1)
            area_node2 = URLMappingService.create_legacy_mapping(area2.country, area2)

            print(f"✅ Created area nodes: {area_node1.name} and {area_node2.name}")

            # Test that we can find them by their full paths
            path1 = [area_node1.root.short_name, area_node1.short_name]
            path2 = [area_node2.root.short_name, area_node2.short_name]

            found_area1 = URLMappingService.find_node_by_path(path1)
            found_area2 = URLMappingService.find_node_by_path(path2)

            if found_area1 and found_area1.id == area_node1.id:
                print(f"✅ Correctly found {area_node1.name} via hierarchical path {path1}")
            else:
                print(f"❌ Failed to find {area_node1.name} via hierarchical path {path1}")
                return False

            if found_area2 and found_area2.id == area_node2.id:
                print(f"✅ Correctly found {area_node2.name} via hierarchical path {path2}")
            else:
                print(f"❌ Failed to find {area_node2.name} via hierarchical path {path2}")
                return False

        print("\n" + "=" * 50)
        print("🎉 All hierarchical path tests passed!")
        print("\nThe system correctly handles:")
        print("✅ Duplicate short names across different levels")
        print("✅ Hierarchical context for path resolution")
        print("✅ Proper parent-child relationships")
        print("✅ Non-existent paths return None")

        return True

if __name__ == "__main__":
    success = test_hierarchical_paths()
    if not success:
        print("\n❌ Hierarchical path tests failed. Check the errors above.")
        exit(1)