#!/usr/bin/env python3
"""
Script to migrate spots and dive shops from legacy geographic fields to new geographic_node_id
"""

import os
import sys

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app import create_app, db
from app.models import DiveShop, GeographicNode, Spot


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
                print(
                    f"  Warning: Could not find geographic node for spot {spot.id} ({spot.name})"
                )

            # Commit every 100 spots to avoid memory issues
            if (i + 1) % 100 == 0:
                db.session.commit()
                print(f"  Committed batch of 100 spots")

        # Final commit
        db.session.commit()

        print(f"\nSpot migration completed!")
        print(f"  Successfully migrated: {migrated_count} spots")
        print(f"  Failed to migrate: {failed_count} spots")


def migrate_dive_shops_to_geographic_nodes():
    """Migrate dive shops to use the new geographic_node_id field"""

    app = create_app()
    with app.app_context():

        print("\nStarting dive shop migration to geographic nodes...")

        # Get all dive shops that need migration
        dive_shops = DiveShop.query.filter(DiveShop.geographic_node_id.is_(None)).all()
        print(f"Found {len(dive_shops)} dive shops to migrate")

        migrated_count = 0
        failed_count = 0

        for i, dive_shop in enumerate(dive_shops):
            if i % 100 == 0:
                print(f"Processing dive shop {i+1}/{len(dive_shops)}...")

            # Find the appropriate geographic node based on legacy fields
            geographic_node = None

            # Try to find by locality first (most specific)
            if dive_shop.locality_id:
                geographic_node = GeographicNode.query.filter_by(
                    legacy_locality_id=dive_shop.locality_id
                ).first()

            # If not found, try area_two
            if not geographic_node and dive_shop.area_two_id:
                geographic_node = GeographicNode.query.filter_by(
                    legacy_area_two_id=dive_shop.area_two_id
                ).first()

            # If not found, try area_one
            if not geographic_node and dive_shop.area_one_id:
                geographic_node = GeographicNode.query.filter_by(
                    legacy_area_one_id=dive_shop.area_one_id
                ).first()

            # If not found, try country
            if not geographic_node and dive_shop.country_id:
                geographic_node = GeographicNode.query.filter_by(
                    legacy_country_id=dive_shop.country_id
                ).first()

            # Update the dive shop
            if geographic_node:
                dive_shop.geographic_node_id = geographic_node.id
                migrated_count += 1
            else:
                failed_count += 1
                print(
                    f"  Warning: Could not find geographic node for dive shop {dive_shop.id} ({dive_shop.name})"
                )

            # Commit every 100 dive shops to avoid memory issues
            if (i + 1) % 100 == 0:
                db.session.commit()
                print(f"  Committed batch of 100 dive shops")

        # Final commit
        db.session.commit()

        print(f"\nDive shop migration completed!")
        print(f"  Successfully migrated: {migrated_count} dive shops")
        print(f"  Failed to migrate: {failed_count} dive shops")


def verify_migration():
    """Verify the migration results"""

    app = create_app()
    with app.app_context():

        print(f"\n=== Migration Verification ===")

        # Verify spots migration
        total_spots = Spot.query.count()
        spots_with_geographic_node = Spot.query.filter(
            Spot.geographic_node_id.isnot(None)
        ).count()
        spots_without_geographic_node = Spot.query.filter(
            Spot.geographic_node_id.is_(None)
        ).count()

        print(f"\nSpots:")
        print(f"  Total spots: {total_spots}")
        print(f"  Spots with geographic_node_id: {spots_with_geographic_node}")
        print(f"  Spots without geographic_node_id: {spots_without_geographic_node}")

        # Verify dive shops migration
        total_dive_shops = DiveShop.query.count()
        dive_shops_with_geographic_node = DiveShop.query.filter(
            DiveShop.geographic_node_id.isnot(None)
        ).count()
        dive_shops_without_geographic_node = DiveShop.query.filter(
            DiveShop.geographic_node_id.is_(None)
        ).count()

        print(f"\nDive Shops:")
        print(f"  Total dive shops: {total_dive_shops}")
        print(
            f"  Dive shops with geographic_node_id: {dive_shops_with_geographic_node}"
        )
        print(
            f"  Dive shops without geographic_node_id: {dive_shops_without_geographic_node}"
        )

        # Test Thailand specifically
        thailand_node = GeographicNode.query.filter_by(short_name="th").first()
        if thailand_node:
            thailand_spots = Spot.query.filter_by(
                geographic_node_id=thailand_node.id
            ).count()
            thailand_dive_shops = DiveShop.query.filter_by(
                geographic_node_id=thailand_node.id
            ).count()
            print(f"\nThailand (new):")
            print(f"  Spots in Thailand: {thailand_spots}")
            print(f"  Dive shops in Thailand: {thailand_dive_shops}")

            # Check descendant spots and dive shops
            descendant_nodes = [thailand_node.id] + [
                desc.id for desc in thailand_node.get_descendants()
            ]
            descendant_spots = Spot.query.filter(
                Spot.geographic_node_id.in_(descendant_nodes)
            ).count()
            descendant_dive_shops = DiveShop.query.filter(
                DiveShop.geographic_node_id.in_(descendant_nodes)
            ).count()
            print(f"  Spots in Thailand and descendants: {descendant_spots}")
            print(f"  Dive shops in Thailand and descendants: {descendant_dive_shops}")


def main():
    """Run the complete migration process"""

    print("Starting migration of spots and dive shops to geographic nodes...")

    # Migrate spots
    migrate_spots_to_geographic_nodes()

    # Migrate dive shops
    migrate_dive_shops_to_geographic_nodes()

    # Verify the migration
    verify_migration()

    print("\nMigration process completed!")


if __name__ == "__main__":
    main()
