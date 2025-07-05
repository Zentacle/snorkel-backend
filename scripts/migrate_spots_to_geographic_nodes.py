#!/usr/bin/env python3
"""
Script to migrate spots from legacy geographic fields to new geographic_node_id
"""

import sys
import os

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Spot, GeographicNode
from sqlalchemy import func

def migrate_spots_to_geographic_nodes():
    """Migrate spots to use the new geographic_node_id field"""

    app = create_app()
    with app.app_context():

        print("Starting spot migration to geographic nodes...")

        # Get all spots that need migration
        spots = Spot.query.filter(Spot.geographic_node_id.is_(None)).all()
        print(f"Found {len(spots)} spots to migrate")

        migrated_count = 0
        failed_count = 0

        for i, spot in enumerate(spots):
            if i % 100 == 0:
                print(f"Processing spot {i+1}/{len(spots)}...")

            # Find the appropriate geographic node based on legacy fields
            geographic_node = None

            # Try to find by locality first (most specific)
            if spot.locality_id:
                geographic_node = GeographicNode.query.filter_by(
                    legacy_locality_id=spot.locality_id
                ).first()

            # If not found, try area_two
            if not geographic_node and spot.area_two_id:
                geographic_node = GeographicNode.query.filter_by(
                    legacy_area_two_id=spot.area_two_id
                ).first()

            # If not found, try area_one
            if not geographic_node and spot.area_one_id:
                geographic_node = GeographicNode.query.filter_by(
                    legacy_area_one_id=spot.area_one_id
                ).first()

            # If not found, try country
            if not geographic_node and spot.country_id:
                geographic_node = GeographicNode.query.filter_by(
                    legacy_country_id=spot.country_id
                ).first()

            # Update the spot
            if geographic_node:
                spot.geographic_node_id = geographic_node.id
                migrated_count += 1
            else:
                failed_count += 1
                print(f"  Warning: Could not find geographic node for spot {spot.id} ({spot.name})")

            # Commit every 100 spots to avoid memory issues
            if (i + 1) % 100 == 0:
                db.session.commit()
                print(f"  Committed batch of 100 spots")

        # Final commit
        db.session.commit()

        print(f"\nMigration completed!")
        print(f"  Successfully migrated: {migrated_count} spots")
        print(f"  Failed to migrate: {failed_count} spots")

        # Verify migration
        total_spots = Spot.query.count()
        spots_with_geographic_node = Spot.query.filter(Spot.geographic_node_id.isnot(None)).count()
        spots_without_geographic_node = Spot.query.filter(Spot.geographic_node_id.is_(None)).count()

        print(f"\nVerification:")
        print(f"  Total spots: {total_spots}")
        print(f"  Spots with geographic_node_id: {spots_with_geographic_node}")
        print(f"  Spots without geographic_node_id: {spots_without_geographic_node}")

        # Test Thailand specifically
        thailand_node = GeographicNode.query.filter_by(short_name='th').first()
        if thailand_node:
            thailand_spots = Spot.query.filter_by(geographic_node_id=thailand_node.id).count()
            print(f"  Spots in Thailand (new): {thailand_spots}")

            # Check descendant spots
            descendant_nodes = [thailand_node.id] + [desc.id for desc in thailand_node.get_descendants()]
            descendant_spots = Spot.query.filter(Spot.geographic_node_id.in_(descendant_nodes)).count()
            print(f"  Spots in Thailand and descendants: {descendant_spots}")

if __name__ == "__main__":
    migrate_spots_to_geographic_nodes()