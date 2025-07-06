#!/usr/bin/env python3
"""
Script to clean orphaned legacy geographic data
Removes area_two, area_one, locality, and country records that have no relationships to spots or dive shops
"""

import os
import sys

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import AreaOne, AreaTwo, Country, DiveShop, Locality, Spot


def find_orphaned_localities():
    """Find localities with no spots or dive shops"""

    app = create_app()
    with app.app_context():

        print("Finding orphaned localities...")

        # Find localities with no spots and no dive shops
        orphaned_localities = (
            db.session.query(Locality)
            .outerjoin(Spot)
            .outerjoin(DiveShop)
            .filter(Spot.id.is_(None), DiveShop.id.is_(None))
            .all()
        )

        print(f"Found {len(orphaned_localities)} orphaned localities")
        return orphaned_localities


def find_orphaned_area_twos():
    """Find area_twos with no spots, dive shops, or localities"""

    app = create_app()
    with app.app_context():

        print("Finding orphaned area_twos...")

        # Find area_twos with no spots, dive shops, or localities
        orphaned_area_twos = (
            db.session.query(AreaTwo)
            .outerjoin(Spot)
            .outerjoin(DiveShop)
            .outerjoin(Locality)
            .filter(Spot.id.is_(None), DiveShop.id.is_(None), Locality.id.is_(None))
            .all()
        )

        print(f"Found {len(orphaned_area_twos)} orphaned area_twos")
        return orphaned_area_twos


def find_orphaned_area_ones():
    """Find area_ones with no spots, dive shops, area_twos, or localities"""

    app = create_app()
    with app.app_context():

        print("Finding orphaned area_ones...")

        # Find area_ones with no spots, dive shops, area_twos, or localities
        orphaned_area_ones = (
            db.session.query(AreaOne)
            .outerjoin(Spot)
            .outerjoin(DiveShop)
            .outerjoin(AreaTwo)
            .outerjoin(Locality)
            .filter(
                Spot.id.is_(None),
                DiveShop.id.is_(None),
                AreaTwo.id.is_(None),
                Locality.id.is_(None),
            )
            .all()
        )

        print(f"Found {len(orphaned_area_ones)} orphaned area_ones")
        return orphaned_area_ones


def find_orphaned_countries():
    """Find countries with no spots, dive shops, area_ones, area_twos, or localities"""

    app = create_app()
    with app.app_context():

        print("Finding orphaned countries...")

        # Find countries with no spots, dive shops, area_ones, area_twos, or localities
        orphaned_countries = (
            db.session.query(Country)
            .outerjoin(Spot)
            .outerjoin(DiveShop)
            .outerjoin(AreaOne)
            .outerjoin(AreaTwo)
            .outerjoin(Locality)
            .filter(
                Spot.id.is_(None),
                DiveShop.id.is_(None),
                AreaOne.id.is_(None),
                AreaTwo.id.is_(None),
                Locality.id.is_(None),
            )
            .all()
        )

        print(f"Found {len(orphaned_countries)} orphaned countries")
        return orphaned_countries


def clean_orphaned_data():
    """Remove all orphaned legacy geographic data"""

    app = create_app()
    with app.app_context():

        print("Cleaning orphaned legacy geographic data...")
        print("=" * 50)

        # Step 1: Find orphaned records
        orphaned_localities = find_orphaned_localities()
        orphaned_area_twos = find_orphaned_area_twos()
        orphaned_area_ones = find_orphaned_area_ones()
        orphaned_countries = find_orphaned_countries()

        total_orphaned = (
            len(orphaned_localities) + len(orphaned_area_twos) + len(orphaned_area_ones) + len(orphaned_countries)
        )

        if total_orphaned == 0:
            print("No orphaned records found!")
            return

        print(f"\nSummary of orphaned records:")
        print(f"  Localities: {len(orphaned_localities)}")
        print(f"  Area Twos: {len(orphaned_area_twos)}")
        print(f"  Area Ones: {len(orphaned_area_ones)}")
        print(f"  Countries: {len(orphaned_countries)}")
        print(f"  Total: {total_orphaned}")

        # Step 2: Show some examples
        print(f"\nExamples of orphaned records:")
        if orphaned_localities:
            second_locality = orphaned_localities[1].name if len(orphaned_localities) > 1 else ""
            print(f"  Localities: {orphaned_localities[0].name}, {second_locality}")
        if orphaned_area_twos:
            second_area_two = orphaned_area_twos[1].name if len(orphaned_area_twos) > 1 else ""
            print(f"  Area Twos: {orphaned_area_twos[0].name}, {second_area_two}")
        if orphaned_area_ones:
            second_area_one = orphaned_area_ones[1].name if len(orphaned_area_ones) > 1 else ""
            print(f"  Area Ones: {orphaned_area_ones[0].name}, {second_area_one}")
        if orphaned_countries:
            second_country = orphaned_countries[1].name if len(orphaned_countries) > 1 else ""
            print(f"  Countries: {orphaned_countries[0].name}, {second_country}")

        # Step 3: Confirm deletion
        response = input(f"\nDelete {total_orphaned} orphaned records? (y/n): ").lower().strip()

        if response != "y":
            print("Operation cancelled.")
            return

        # Step 4: Delete orphaned records (in reverse dependency order)
        print("\nDeleting orphaned records...")

        deleted_count = 0

        # Delete localities first (they depend on area_twos)
        for locality in orphaned_localities:
            db.session.delete(locality)
            deleted_count += 1

        # Delete area_twos (they depend on area_ones)
        for area_two in orphaned_area_twos:
            db.session.delete(area_two)
            deleted_count += 1

        # Delete area_ones (they depend on countries)
        for area_one in orphaned_area_ones:
            db.session.delete(area_one)
            deleted_count += 1

        # Delete countries last
        for country in orphaned_countries:
            db.session.delete(country)
            deleted_count += 1

        # Commit all deletions
        db.session.commit()

        print(f"Successfully deleted {deleted_count} orphaned records!")

        # Step 5: Verify cleanup
        print("\nVerifying cleanup...")
        remaining_localities = find_orphaned_localities()
        remaining_area_twos = find_orphaned_area_twos()
        remaining_area_ones = find_orphaned_area_ones()
        remaining_countries = find_orphaned_countries()

        total_remaining = (
            len(remaining_localities) + len(remaining_area_twos) + len(remaining_area_ones) + len(remaining_countries)
        )

        if total_remaining == 0:
            print("✓ All orphaned records successfully removed!")
        else:
            print(f"⚠ {total_remaining} orphaned records still remain (may have circular dependencies)")


def check_data_integrity():
    """Check for any remaining data integrity issues"""

    app = create_app()
    with app.app_context():

        print("\nChecking data integrity...")

        # Check for area_twos without area_one_id
        orphaned_area_twos = AreaTwo.query.filter(AreaTwo.country_id.isnot(None), AreaTwo.area_one_id.is_(None)).count()

        # Check for localities without area_two_id
        orphaned_localities = Locality.query.filter(
            Locality.country_id.isnot(None), Locality.area_two_id.is_(None)
        ).count()

        print(f"  Area_twos without area_one_id: {orphaned_area_twos}")
        print(f"  Localities without area_two_id: {orphaned_localities}")

        if orphaned_area_twos == 0 and orphaned_localities == 0:
            print("✓ All geographic records have proper relationships!")
        else:
            print("⚠ Some geographic records still have missing relationships")


if __name__ == "__main__":
    print("Legacy Geographic Data Cleanup Script")
    print("=" * 40)

    # Clean orphaned data
    clean_orphaned_data()

    # Check data integrity
    check_data_integrity()

    print("\nScript completed!")
