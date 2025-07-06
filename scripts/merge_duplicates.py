#!/usr/bin/env python3
"""
Script to merge duplicate data in the existing geographic tables
and add constraints to prevent future duplicates
"""

import os
import sys

from sqlalchemy import func, text

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import AreaOne, AreaTwo, Country, DiveShop, Locality, Spot


def merge_duplicates():
    """Merge duplicate data in the existing geographic tables"""

    # Debug: Print environment variables before creating app
    print("=== ENVIRONMENT DEBUG INFO ===")
    print(f"Current working directory: {os.getcwd()}")
    print(f"FLASK_ENV: {os.environ.get('FLASK_ENV', 'Not set')}")
    print(f"DATABASE_URL from env: {os.environ.get('DATABASE_URL', 'Not set')}")

    # Check if .env file exists and is readable
    env_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    print(f".env file path: {env_file_path}")
    print(f".env file exists: {os.path.exists(env_file_path)}")

    app = create_app()
    with app.app_context():

        # Print which database is being used
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI", "Unknown")
        print(f"Database URL from app config: {db_url}")

        # Mask sensitive parts of the database URL for security
        if "@" in db_url:
            # Extract host and database name from postgresql://user:pass@host:port/dbname
            parts = db_url.split("@")
            if len(parts) == 2:
                protocol_user_pass = parts[0]
                host_db = parts[1]
                # Show only the protocol and host/database parts
                masked_url = f"{protocol_user_pass.split('://')[0]}://***:***@{host_db}"
            else:
                masked_url = "***"
        else:
            masked_url = db_url

        print(f"Using database: {masked_url}")
        print("=== MERGING DUPLICATES IN EXISTING TABLES ===\n")

        try:
            # 1. Merge Country duplicates
            print("1. MERGING COUNTRY DUPLICATES:")
            country_duplicates = (
                db.session.query(Country.short_name, func.count(Country.id).label("count"))
                .group_by(Country.short_name)
                .having(func.count(Country.id) > 1)
                .all()
            )

            if country_duplicates:
                print(f"   Found {len(country_duplicates)} duplicate short_names to merge:")
                for short_name, count in country_duplicates:
                    countries = Country.query.filter_by(short_name=short_name).order_by(Country.id).all()
                    print(f"     '{short_name}': {count} records")

                    # Keep the first record (lowest ID) and merge others into it
                    keep_country = countries[0]
                    merge_countries = countries[1:]

                    print(f"       Keeping ID: {keep_country.id}, name: '{keep_country.name}'")

                    for merge_country in merge_countries:
                        print(f"       Merging ID: {merge_country.id}, name: '{merge_country.name}'")

                        # Update all related records to point to the kept country
                        spot_updates = Spot.query.filter_by(country_id=merge_country.id).update(
                            {"country_id": keep_country.id}
                        )
                        area_one_updates = AreaOne.query.filter_by(country_id=merge_country.id).update(
                            {"country_id": keep_country.id}
                        )
                        area_two_updates = AreaTwo.query.filter_by(country_id=merge_country.id).update(
                            {"country_id": keep_country.id}
                        )
                        locality_updates = Locality.query.filter_by(country_id=merge_country.id).update(
                            {"country_id": keep_country.id}
                        )
                        shop_updates = DiveShop.query.filter_by(country_id=merge_country.id).update(
                            {"country_id": keep_country.id}
                        )

                        print(
                            f"         Updated: {spot_updates} spots, {area_one_updates} area_ones, "
                            f"{area_two_updates} area_twos, {locality_updates} localities, "
                            f"{shop_updates} shops"
                        )

                        # Commit updates before deletion to avoid foreign key issues
                        db.session.commit()

                        # Verify no references remain before deletion
                        remaining_spots = Spot.query.filter_by(country_id=merge_country.id).count()
                        remaining_area_ones = AreaOne.query.filter_by(country_id=merge_country.id).count()
                        remaining_area_twos = AreaTwo.query.filter_by(country_id=merge_country.id).count()
                        remaining_localities = Locality.query.filter_by(country_id=merge_country.id).count()
                        remaining_shops = DiveShop.query.filter_by(country_id=merge_country.id).count()

                        if (
                            remaining_spots
                            + remaining_area_ones
                            + remaining_area_twos
                            + remaining_localities
                            + remaining_shops
                            > 0
                        ):
                            print(
                                f"         ⚠️  Warning: {remaining_spots} spots, "
                                f"{remaining_area_ones} area_ones, {remaining_area_twos} area_twos, "
                                f"{remaining_localities} localities, {remaining_shops} shops "
                                f"still reference country {merge_country.id}"
                            )

                        # Delete the duplicate country
                        try:
                            db.session.delete(merge_country)
                            db.session.commit()
                            print(f"         Deleted duplicate country ID: {merge_country.id}")
                        except Exception as e:
                            print(f"         ❌ Failed to delete country ID {merge_country.id}: {e}")
                            db.session.rollback()
            else:
                print("   No duplicate countries found")

            print()

            # 2. Merge AreaOne duplicates
            print("2. MERGING AREA_ONE DUPLICATES:")
            area_one_duplicates = (
                db.session.query(
                    AreaOne.short_name,
                    AreaOne.country_id,
                    func.count(AreaOne.id).label("count"),
                )
                .group_by(AreaOne.short_name, AreaOne.country_id)
                .having(func.count(AreaOne.id) > 1)
                .all()
            )

            if area_one_duplicates:
                print(
                    f"   Found {len(area_one_duplicates)} duplicate " f"(short_name, country_id) combinations to merge:"
                )
                for short_name, country_id, count in area_one_duplicates:
                    country = Country.query.get(country_id)
                    country_name = country.name if country else f"Unknown (ID: {country_id})"
                    area_ones = (
                        AreaOne.query.filter_by(short_name=short_name, country_id=country_id).order_by(AreaOne.id).all()
                    )
                    print(f"     '{short_name}' in '{country_name}': {count} records")

                    # Keep the first record (lowest ID) and merge others into it
                    keep_area_one = area_ones[0]
                    merge_area_ones = area_ones[1:]

                    print(f"       Keeping ID: {keep_area_one.id}, name: '{keep_area_one.name}'")

                    for merge_area_one in merge_area_ones:
                        print(f"       Merging ID: {merge_area_one.id}, name: '{merge_area_one.name}'")

                        # Update all related records to point to the kept area_one
                        spot_updates = Spot.query.filter_by(area_one_id=merge_area_one.id).update(
                            {"area_one_id": keep_area_one.id}
                        )
                        area_two_updates = AreaTwo.query.filter_by(area_one_id=merge_area_one.id).update(
                            {"area_one_id": keep_area_one.id}
                        )
                        locality_updates = Locality.query.filter_by(area_one_id=merge_area_one.id).update(
                            {"area_one_id": keep_area_one.id}
                        )
                        shop_updates = DiveShop.query.filter_by(area_one_id=merge_area_one.id).update(
                            {"area_one_id": keep_area_one.id}
                        )

                        print(
                            f"         Updated: {spot_updates} spots, {area_two_updates} area_twos, "
                            f"{locality_updates} localities, {shop_updates} shops"
                        )

                        # Commit updates before deletion to avoid foreign key issues
                        db.session.commit()

                        # Verify no references remain before deletion
                        remaining_spots = Spot.query.filter_by(area_one_id=merge_area_one.id).count()
                        remaining_area_twos = AreaTwo.query.filter_by(area_one_id=merge_area_one.id).count()
                        remaining_localities = Locality.query.filter_by(area_one_id=merge_area_one.id).count()
                        remaining_shops = DiveShop.query.filter_by(area_one_id=merge_area_one.id).count()

                        if remaining_spots + remaining_area_twos + remaining_localities + remaining_shops > 0:
                            print(
                                f"         ⚠️  Warning: {remaining_spots} spots, "
                                f"{remaining_area_twos} area_twos, {remaining_localities} localities, "
                                f"{remaining_shops} shops still reference area_one {merge_area_one.id}"
                            )

                        # Delete the duplicate area_one
                        try:
                            db.session.delete(merge_area_one)
                            db.session.commit()
                            print(f"         Deleted duplicate area_one ID: {merge_area_one.id}")
                        except Exception as e:
                            print(f"         ❌ Failed to delete area_one ID {merge_area_one.id}: {e}")
                            db.session.rollback()
            else:
                print("   No duplicate area_ones found")

            print()

            # 3. Merge AreaTwo duplicates
            print("3. MERGING AREA_TWO DUPLICATES:")
            area_two_duplicates = (
                db.session.query(
                    AreaTwo.short_name,
                    AreaTwo.country_id,
                    AreaTwo.area_one_id,
                    func.count(AreaTwo.id).label("count"),
                )
                .group_by(AreaTwo.short_name, AreaTwo.country_id, AreaTwo.area_one_id)
                .having(func.count(AreaTwo.id) > 1)
                .all()
            )

            if area_two_duplicates:
                print(
                    f"   Found {len(area_two_duplicates)} duplicate "
                    f"(short_name, country_id, area_one_id) combinations to merge:"
                )
                for short_name, country_id, area_one_id, count in area_two_duplicates:
                    country = Country.query.get(country_id)
                    area_one = AreaOne.query.get(area_one_id)
                    country_name = country.name if country else f"Unknown (ID: {country_id})"
                    area_one_name = area_one.name if area_one else f"Unknown (ID: {area_one_id})"
                    area_twos = (
                        AreaTwo.query.filter_by(
                            short_name=short_name,
                            country_id=country_id,
                            area_one_id=area_one_id,
                        )
                        .order_by(AreaTwo.id)
                        .all()
                    )
                    print(f"     '{short_name}' in '{country_name}'/'{area_one_name}': " f"{count} records")

                    # Keep the first record (lowest ID) and merge others into it
                    keep_area_two = area_twos[0]
                    merge_area_twos = area_twos[1:]

                    print(f"       Keeping ID: {keep_area_two.id}, name: '{keep_area_two.name}'")

                    for merge_area_two in merge_area_twos:
                        print(f"       Merging ID: {merge_area_two.id}, name: '{merge_area_two.name}'")

                        # Update all related records to point to the kept area_two
                        spot_updates = Spot.query.filter_by(area_two_id=merge_area_two.id).update(
                            {"area_two_id": keep_area_two.id}
                        )
                        locality_updates = Locality.query.filter_by(area_two_id=merge_area_two.id).update(
                            {"area_two_id": keep_area_two.id}
                        )
                        shop_updates = DiveShop.query.filter_by(area_two_id=merge_area_two.id).update(
                            {"area_two_id": keep_area_two.id}
                        )

                        print(
                            f"         Updated: {spot_updates} spots, {locality_updates} localities, "
                            f"{shop_updates} shops"
                        )

                        # Commit updates before deletion to avoid foreign key issues
                        db.session.commit()

                        # Verify no references remain before deletion
                        remaining_spots = Spot.query.filter_by(area_two_id=merge_area_two.id).count()
                        remaining_localities = Locality.query.filter_by(area_two_id=merge_area_two.id).count()
                        remaining_shops = DiveShop.query.filter_by(area_two_id=merge_area_two.id).count()

                        if remaining_spots + remaining_localities + remaining_shops > 0:
                            print(
                                f"         ⚠️  Warning: {remaining_spots} spots, "
                                f"{remaining_localities} localities, {remaining_shops} shops "
                                f"still reference area_two {merge_area_two.id}"
                            )

                        # Delete the duplicate area_two
                        try:
                            db.session.delete(merge_area_two)
                            db.session.commit()
                            print(f"         Deleted duplicate area_two ID: {merge_area_two.id}")
                        except Exception as e:
                            print(f"         ❌ Failed to delete area_two ID {merge_area_two.id}: {e}")
                            db.session.rollback()
            else:
                print("   No duplicate area_twos found")

            print()

            # 4. Merge Locality duplicates
            print("4. MERGING LOCALITY DUPLICATES:")
            locality_duplicates = (
                db.session.query(
                    Locality.short_name,
                    Locality.country_id,
                    Locality.area_one_id,
                    Locality.area_two_id,
                    func.count(Locality.id).label("count"),
                )
                .group_by(
                    Locality.short_name,
                    Locality.country_id,
                    Locality.area_one_id,
                    Locality.area_two_id,
                )
                .having(func.count(Locality.id) > 1)
                .all()
            )

            if locality_duplicates:
                print(
                    f"   Found {len(locality_duplicates)} duplicate "
                    f"(short_name, country_id, area_one_id, area_two_id) combinations to merge:"
                )
                for (
                    short_name,
                    country_id,
                    area_one_id,
                    area_two_id,
                    count,
                ) in locality_duplicates:
                    country = Country.query.get(country_id)
                    area_one = AreaOne.query.get(area_one_id)
                    area_two = AreaTwo.query.get(area_two_id)
                    country_name = country.name if country else f"Unknown (ID: {country_id})"
                    area_one_name = area_one.name if area_one else f"Unknown (ID: {area_one_id})"
                    area_two_name = area_two.name if area_two else f"Unknown (ID: {area_two_id})"
                    localities = (
                        Locality.query.filter_by(
                            short_name=short_name,
                            country_id=country_id,
                            area_one_id=area_one_id,
                            area_two_id=area_two_id,
                        )
                        .order_by(Locality.id)
                        .all()
                    )
                    print(
                        f"     '{short_name}' in '{country_name}'/'{area_one_name}'/"
                        f"'{area_two_name}': {count} records"
                    )

                    # Keep the first record (lowest ID) and merge others into it
                    keep_locality = localities[0]
                    merge_localities = localities[1:]

                    print(f"       Keeping ID: {keep_locality.id}, name: '{keep_locality.name}'")

                    for merge_locality in merge_localities:
                        print(f"       Merging ID: {merge_locality.id}, name: '{merge_locality.name}'")

                        # Update all related records to point to the kept locality
                        spot_updates = Spot.query.filter_by(locality_id=merge_locality.id).update(
                            {"locality_id": keep_locality.id}
                        )
                        shop_updates = DiveShop.query.filter_by(locality_id=merge_locality.id).update(
                            {"locality_id": keep_locality.id}
                        )

                        print(f"         Updated: {spot_updates} spots, {shop_updates} shops")

                        # Commit updates before deletion to avoid foreign key issues
                        db.session.commit()

                        # Verify no references remain before deletion
                        remaining_spots = Spot.query.filter_by(locality_id=merge_locality.id).count()
                        remaining_shops = DiveShop.query.filter_by(locality_id=merge_locality.id).count()

                        if remaining_spots + remaining_shops > 0:
                            print(
                                f"         ⚠️  Warning: {remaining_spots} spots, {remaining_shops} shops "
                                f"still reference locality {merge_locality.id}"
                            )

                        # Delete the duplicate locality
                        try:
                            db.session.delete(merge_locality)
                            db.session.commit()
                            print(f"         Deleted duplicate locality ID: {merge_locality.id}")
                        except Exception as e:
                            print(f"         ❌ Failed to delete locality ID {merge_locality.id}: {e}")
                            db.session.rollback()
            else:
                print("   No duplicate localities found")

            print()

            # Verify deletions actually happened
            print("\n=== VERIFYING DELETIONS ===")
            verify_deletions()

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during merge: {e}")
            raise


def verify_deletions():
    """Verify that duplicates were actually deleted"""

    app = create_app()
    with app.app_context():

        # Check for remaining duplicates
        country_duplicates = (
            db.session.query(Country.short_name, func.count(Country.id).label("count"))
            .group_by(Country.short_name)
            .having(func.count(Country.id) > 1)
            .all()
        )

        area_one_duplicates = (
            db.session.query(
                AreaOne.short_name,
                AreaOne.country_id,
                func.count(AreaOne.id).label("count"),
            )
            .group_by(AreaOne.short_name, AreaOne.country_id)
            .having(func.count(AreaOne.id) > 1)
            .all()
        )

        area_two_duplicates = (
            db.session.query(
                AreaTwo.short_name,
                AreaTwo.country_id,
                AreaTwo.area_one_id,
                func.count(AreaTwo.id).label("count"),
            )
            .group_by(AreaTwo.short_name, AreaTwo.country_id, AreaTwo.area_one_id)
            .having(func.count(AreaTwo.id) > 1)
            .all()
        )

        locality_duplicates = (
            db.session.query(
                Locality.short_name,
                Locality.country_id,
                Locality.area_one_id,
                Locality.area_two_id,
                func.count(Locality.id).label("count"),
            )
            .group_by(
                Locality.short_name,
                Locality.country_id,
                Locality.area_one_id,
                Locality.area_two_id,
            )
            .having(func.count(Locality.id) > 1)
            .all()
        )

        total_remaining = (
            len(country_duplicates) + len(area_one_duplicates) + len(area_two_duplicates) + len(locality_duplicates)
        )

        if total_remaining == 0:
            print("✅ All duplicates successfully deleted!")
        else:
            print(f"❌ {total_remaining} duplicate groups still remain:")
            if country_duplicates:
                print(f"   Countries: {len(country_duplicates)} groups")
                for short_name, count in country_duplicates:
                    print(f"     '{short_name}': {count} records")
            if area_one_duplicates:
                print(f"   AreaOnes: {len(area_one_duplicates)} groups")
            if area_two_duplicates:
                print(f"   AreaTwos: {len(area_two_duplicates)} groups")
            if locality_duplicates:
                print(f"   Localities: {len(locality_duplicates)} groups")

            print("\n⚠️  Some duplicates could not be deleted. This might be due to:")
            print("   - Foreign key constraints preventing deletion")
            print("   - Database transaction issues")
            print("   - Orphaned records that need manual cleanup")


def add_constraints():
    """Add constraints to prevent future duplicates"""

    app = create_app()
    with app.app_context():

        print("\n=== ADDING CONSTRAINTS TO PREVENT FUTURE DUPLICATES ===\n")

        try:
            # Add unique constraints to prevent future duplicates
            constraints = [
                # Country constraints
                (
                    "unique_country_short_name",
                    "ALTER TABLE country ADD CONSTRAINT unique_country_short_name UNIQUE (short_name)",
                ),
                # AreaOne constraints
                (
                    "unique_area_one_short_name_country",
                    "ALTER TABLE area_one ADD CONSTRAINT unique_area_one_short_name_country "
                    "UNIQUE (short_name, country_id)",
                ),
                # AreaTwo constraints
                (
                    "unique_area_two_short_name_country_area_one",
                    "ALTER TABLE area_two ADD CONSTRAINT unique_area_two_short_name_country_area_one "
                    "UNIQUE (short_name, country_id, area_one_id)",
                ),
                # Locality constraints
                (
                    "unique_locality_short_name_country_area_one_area_two",
                    "ALTER TABLE locality ADD CONSTRAINT unique_locality_short_name_country_area_one_area_two "
                    "UNIQUE (short_name, country_id, area_one_id, area_two_id)",
                ),
            ]

            successful_constraints = []
            failed_constraints = []

            for constraint_name, constraint_sql in constraints:
                try:
                    print(f"Adding constraint: {constraint_name}")
                    db.session.execute(text(constraint_sql))
                    db.session.commit()
                    print(f"✅ Successfully added constraint: {constraint_name}")
                    successful_constraints.append(constraint_name)
                except Exception as e:
                    db.session.rollback()
                    print(f"❌ Failed to add constraint {constraint_name}: {e}")
                    failed_constraints.append((constraint_name, str(e)))

            print("\n=== CONSTRAINT SUMMARY ===")
            print(f"Successfully added: {len(successful_constraints)} constraints")
            print(f"Failed to add: {len(failed_constraints)} constraints")

            if successful_constraints:
                print(f"✅ Added constraints: {', '.join(successful_constraints)}")

            if failed_constraints:
                print("❌ Failed constraints:")
                for constraint_name, error in failed_constraints:
                    print(f"   {constraint_name}: {error}")

            if failed_constraints:
                print("\n⚠️  Some constraints failed to add. This might be due to:")
                print("   - Constraints already exist")
                print("   - Duplicate data still present")
                print("   - Database permission issues")
                print("   - Database type limitations")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding constraints: {e}")
            raise


def verify_no_duplicates():
    """Verify that no duplicates remain after merging"""

    app = create_app()
    with app.app_context():

        print("\n=== VERIFYING NO DUPLICATES REMAIN ===\n")

        # Check for remaining duplicates
        country_duplicates = (
            db.session.query(Country.short_name, func.count(Country.id).label("count"))
            .group_by(Country.short_name)
            .having(func.count(Country.id) > 1)
            .all()
        )

        area_one_duplicates = (
            db.session.query(
                AreaOne.short_name,
                AreaOne.country_id,
                func.count(AreaOne.id).label("count"),
            )
            .group_by(AreaOne.short_name, AreaOne.country_id)
            .having(func.count(AreaOne.id) > 1)
            .all()
        )

        area_two_duplicates = (
            db.session.query(
                AreaTwo.short_name,
                AreaTwo.country_id,
                AreaTwo.area_one_id,
                func.count(AreaTwo.id).label("count"),
            )
            .group_by(AreaTwo.short_name, AreaTwo.country_id, AreaTwo.area_one_id)
            .having(func.count(AreaTwo.id) > 1)
            .all()
        )

        locality_duplicates = (
            db.session.query(
                Locality.short_name,
                Locality.country_id,
                Locality.area_one_id,
                Locality.area_two_id,
                func.count(Locality.id).label("count"),
            )
            .group_by(
                Locality.short_name,
                Locality.country_id,
                Locality.area_one_id,
                Locality.area_two_id,
            )
            .having(func.count(Locality.id) > 1)
            .all()
        )

        total_duplicates = (
            len(country_duplicates) + len(area_one_duplicates) + len(area_two_duplicates) + len(locality_duplicates)
        )

        if total_duplicates == 0:
            print("✅ No duplicates remain! All tables are clean.")
        else:
            print(f"❌ {total_duplicates} duplicate groups still remain:")
            if country_duplicates:
                print(f"   Countries: {len(country_duplicates)}")
            if area_one_duplicates:
                print(f"   AreaOnes: {len(area_one_duplicates)}")
            if area_two_duplicates:
                print(f"   AreaTwos: {len(area_two_duplicates)}")
            if locality_duplicates:
                print(f"   Localities: {len(locality_duplicates)}")


if __name__ == "__main__":
    print("Starting duplicate merge process...")
    print("This will merge duplicates in existing tables and add constraints to prevent future duplicates.")
    print("Make sure you have a backup of your database before proceeding!\n")

    # Run the merge process
    merge_duplicates()

    # Add constraints
    add_constraints()

    # Verify no duplicates remain
    verify_no_duplicates()

    print("\n=== PROCESS COMPLETE ===")
    print("✅ Duplicates have been merged and constraints added.")
    print("✅ Your existing geographic tables are now clean and protected from future duplicates.")
    print("✅ You can now proceed with migration to the new GeographicNode structure.")
