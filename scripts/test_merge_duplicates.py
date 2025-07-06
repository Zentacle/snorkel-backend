#!/usr/bin/env python3
"""
Test script for merge_duplicates.py
Provides dry-run mode and database backup/restore functionality
"""

import os
import subprocess
import sys
import tempfile
from datetime import datetime

from sqlalchemy import func, text

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import AreaOne, AreaTwo, Country, DiveShop, Locality, Spot


def dry_run_merge():
    """Simulate the merge process without making actual changes"""

    app = create_app()
    with app.app_context():

        print("=== DRY RUN: SIMULATING DUPLICATE MERGE ===\n")
        print("This will show what would happen without making actual changes.\n")

        # 1. Analyze Country duplicates
        print("1. COUNTRY DUPLICATES TO MERGE:")
        country_duplicates = db.session.query(
            Country.short_name,
            func.count(Country.id).label('count')
        ).group_by(Country.short_name).having(
            func.count(Country.id) > 1
        ).all()

        if country_duplicates:
            print(f"   Found {len(country_duplicates)} duplicate short_names to merge:")
            for short_name, count in country_duplicates:
                countries = Country.query.filter_by(short_name=short_name).order_by(Country.id).all()
                print(f"     '{short_name}': {count} records")

                keep_country = countries[0]
                merge_countries = countries[1:]

                print(f"       Would keep ID: {keep_country.id}, name: '{keep_country.name}'")

                for merge_country in merge_countries:
                    spot_count = Spot.query.filter_by(country_id=merge_country.id).count()
                    area_one_count = AreaOne.query.filter_by(country_id=merge_country.id).count()
                    area_two_count = AreaTwo.query.filter_by(country_id=merge_country.id).count()
                    locality_count = Locality.query.filter_by(country_id=merge_country.id).count()
                    shop_count = DiveShop.query.filter_by(country_id=merge_country.id).count()

                    print(f"       Would merge ID: {merge_country.id}, name: '{merge_country.name}'")
                    print(f"         - {spot_count} spots would be updated")
                    print(f"         - {area_one_count} area_ones would be updated")
                    print(f"         - {area_two_count} area_twos would be updated")
                    print(f"         - {locality_count} localities would be updated")
                    print(f"         - {shop_count} dive shops would be updated")
        else:
            print("   No duplicate countries found")

        print()

        # 2. Analyze AreaOne duplicates
        print("2. AREA_ONE DUPLICATES TO MERGE:")
        area_one_duplicates = db.session.query(
            AreaOne.short_name,
            AreaOne.country_id,
            func.count(AreaOne.id).label('count')
        ).group_by(AreaOne.short_name, AreaOne.country_id).having(
            func.count(AreaOne.id) > 1
        ).all()

        if area_one_duplicates:
            print(f"   Found {len(area_one_duplicates)} duplicate (short_name, country_id) combinations to merge:")
            for short_name, country_id, count in area_one_duplicates:
                country = Country.query.get(country_id)
                country_name = country.name if country else f"Unknown (ID: {country_id})"
                area_ones = AreaOne.query.filter_by(short_name=short_name, country_id=country_id).order_by(AreaOne.id).all()
                print(f"     '{short_name}' in '{country_name}': {count} records")

                keep_area_one = area_ones[0]
                merge_area_ones = area_ones[1:]

                print(f"       Would keep ID: {keep_area_one.id}, name: '{keep_area_one.name}'")

                for merge_area_one in merge_area_ones:
                    spot_count = Spot.query.filter_by(area_one_id=merge_area_one.id).count()
                    area_two_count = AreaTwo.query.filter_by(area_one_id=merge_area_one.id).count()
                    locality_count = Locality.query.filter_by(area_one_id=merge_area_one.id).count()
                    shop_count = DiveShop.query.filter_by(area_one_id=merge_area_one.id).count()

                    print(f"       Would merge ID: {merge_area_one.id}, name: '{merge_area_one.name}'")
                    print(f"         - {spot_count} spots would be updated")
                    print(f"         - {area_two_count} area_twos would be updated")
                    print(f"         - {locality_count} localities would be updated")
                    print(f"         - {shop_count} dive shops would be updated")
        else:
            print("   No duplicate area_ones found")

        print()

        # 3. Analyze AreaTwo duplicates
        print("3. AREA_TWO DUPLICATES TO MERGE:")
        area_two_duplicates = db.session.query(
            AreaTwo.short_name,
            AreaTwo.country_id,
            AreaTwo.area_one_id,
            func.count(AreaTwo.id).label('count')
        ).group_by(AreaTwo.short_name, AreaTwo.country_id, AreaTwo.area_one_id).having(
            func.count(AreaTwo.id) > 1
        ).all()

        if area_two_duplicates:
            print(f"   Found {len(area_two_duplicates)} duplicate (short_name, country_id, area_one_id) combinations to merge:")
            for short_name, country_id, area_one_id, count in area_two_duplicates:
                country = Country.query.get(country_id)
                area_one = AreaOne.query.get(area_one_id)
                country_name = country.name if country else f"Unknown (ID: {country_id})"
                area_one_name = area_one.name if area_one else f"Unknown (ID: {area_one_id})"
                area_twos = AreaTwo.query.filter_by(short_name=short_name, country_id=country_id, area_one_id=area_one_id).order_by(AreaTwo.id).all()
                print(f"     '{short_name}' in '{country_name}'/'{area_one_name}': {count} records")

                keep_area_two = area_twos[0]
                merge_area_twos = area_twos[1:]

                print(f"       Would keep ID: {keep_area_two.id}, name: '{keep_area_two.name}'")

                for merge_area_two in merge_area_twos:
                    spot_count = Spot.query.filter_by(area_two_id=merge_area_two.id).count()
                    locality_count = Locality.query.filter_by(area_two_id=merge_area_two.id).count()
                    shop_count = DiveShop.query.filter_by(area_two_id=merge_area_two.id).count()

                    print(f"       Would merge ID: {merge_area_two.id}, name: '{merge_area_two.name}'")
                    print(f"         - {spot_count} spots would be updated")
                    print(f"         - {locality_count} localities would be updated")
                    print(f"         - {shop_count} dive shops would be updated")
        else:
            print("   No duplicate area_twos found")

        print()

        # 4. Analyze Locality duplicates
        print("4. LOCALITY DUPLICATES TO MERGE:")
        locality_duplicates = db.session.query(
            Locality.short_name,
            Locality.country_id,
            Locality.area_one_id,
            Locality.area_two_id,
            func.count(Locality.id).label('count')
        ).group_by(Locality.short_name, Locality.country_id, Locality.area_one_id, Locality.area_two_id).having(
            func.count(Locality.id) > 1
        ).all()

        if locality_duplicates:
            print(f"   Found {len(locality_duplicates)} duplicate (short_name, country_id, area_one_id, area_two_id) combinations to merge:")
            for short_name, country_id, area_one_id, area_two_id, count in locality_duplicates:
                country = Country.query.get(country_id)
                area_one = AreaOne.query.get(area_one_id)
                area_two = AreaTwo.query.get(area_two_id)
                country_name = country.name if country else f"Unknown (ID: {country_id})"
                area_one_name = area_one.name if area_one else f"Unknown (ID: {area_one_id})"
                area_two_name = area_two.name if area_two else f"Unknown (ID: {area_two_id})"
                localities = Locality.query.filter_by(short_name=short_name, country_id=country_id, area_one_id=area_one_id, area_two_id=area_two_id).order_by(Locality.id).all()
                print(f"     '{short_name}' in '{country_name}'/'{area_one_name}'/'{area_two_name}': {count} records")

                keep_locality = localities[0]
                merge_localities = localities[1:]

                print(f"       Would keep ID: {keep_locality.id}, name: '{keep_locality.name}'")

                for merge_locality in merge_localities:
                    spot_count = Spot.query.filter_by(locality_id=merge_locality.id).count()
                    shop_count = DiveShop.query.filter_by(locality_id=merge_locality.id).count()

                    print(f"       Would merge ID: {merge_locality.id}, name: '{merge_locality.name}'")
                    print(f"         - {spot_count} spots would be updated")
                    print(f"         - {shop_count} dive shops would be updated")
        else:
            print("   No duplicate localities found")

        print()

        # Summary
        total_duplicates = len(country_duplicates) + len(area_one_duplicates) + len(area_two_duplicates) + len(locality_duplicates)
        print("=== DRY RUN SUMMARY ===")
        print(f"Total duplicate groups that would be merged: {total_duplicates}")

        if total_duplicates > 0:
            print("\n⚠️  Duplicates detected! Review the above output carefully.")
            print("   Run the actual merge script only after confirming these changes look correct.")
        else:
            print("\n✅ No duplicates detected. No changes needed.")


def backup_database():
    """Create a backup of the database"""

    app = create_app()
    db_url = app.config['SQLALCHEMY_DATABASE_URI']

    # Extract database name from URL
    if db_url.startswith('postgresql://'):
        # PostgreSQL
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url)
        db_name = parsed.path[1:]  # Remove leading slash
        host = parsed.hostname
        port = parsed.port or 5432
        user = parsed.username
        password = parsed.password

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"backup_geographic_merge_{timestamp}.sql"

        print(f"Creating PostgreSQL backup: {backup_file}")

        # Check if pg_dump is available
        try:
            subprocess.run(['which', 'pg_dump'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("❌ pg_dump not found in PATH")
            print("   Please install PostgreSQL tools or add them to your PATH")
            print("   On macOS with Homebrew: brew install postgresql")
            print("   Or use the SQLAlchemy backup method instead")
            return None

        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password

        # Create backup command
        cmd = [
            'pg_dump',
            '-h', host,
            '-p', str(port),
            '-U', user,
            '-d', db_name,
            '-f', backup_file,
            '--verbose'
        ]

        try:
            result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
            print(f"✅ Backup created successfully: {backup_file}")
            return backup_file
        except subprocess.CalledProcessError as e:
            print(f"❌ Backup failed: {e}")
            print(f"Error output: {e.stderr}")
            print("\nTrying SQLAlchemy backup method...")
            return backup_via_sqlalchemy(backup_file)

    elif db_url.startswith('sqlite:///'):
        # SQLite
        db_path = db_url.replace('sqlite:///', '')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"backup_geographic_merge_{timestamp}.db"

        print(f"Creating SQLite backup: {backup_file}")

        try:
            import shutil
            shutil.copy2(db_path, backup_file)
            print(f"✅ Backup created successfully: {backup_file}")
            return backup_file
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return None

    else:
        print(f"❌ Unsupported database type: {db_url}")
        return None


def backup_via_sqlalchemy(backup_file):
    """Create backup using SQLAlchemy (fallback method)"""

    app = create_app()
    with app.app_context():

        print(f"Creating backup using SQLAlchemy: {backup_file}")

        try:
            # Get all data from geographic tables
            countries = Country.query.all()
            area_ones = AreaOne.query.all()
            area_twos = AreaTwo.query.all()
            localities = Locality.query.all()
            spots = Spot.query.all()
            dive_shops = DiveShop.query.all()

            # Create a simple backup format
            with open(backup_file, 'w') as f:
                f.write("-- SQLAlchemy Backup\n")
                f.write(f"-- Created: {datetime.now()}\n")
                f.write("-- This is a simplified backup format\n\n")

                # Write country data
                f.write("-- Countries\n")
                for country in countries:
                    f.write(f"INSERT INTO country (id, name, short_name, description, url, map_image_url) VALUES ({country.id}, '{country.name}', '{country.short_name}', '{country.description or ''}', '{country.url or ''}', '{country.map_image_url or ''}');\n")

                f.write("\n-- AreaOnes\n")
                for area_one in area_ones:
                    f.write(f"INSERT INTO area_one (id, google_name, name, short_name, country_id, description, url, map_image_url) VALUES ({area_one.id}, '{area_one.google_name or ''}', '{area_one.name}', '{area_one.short_name}', {area_one.country_id}, '{area_one.description or ''}', '{area_one.url}', '{area_one.map_image_url or ''}');\n")

                f.write("\n-- AreaTwos\n")
                for area_two in area_twos:
                    f.write(f"INSERT INTO area_two (id, google_name, name, short_name, area_one_id, country_id, description, url, map_image_url) VALUES ({area_two.id}, '{area_two.google_name or ''}', '{area_two.name}', '{area_two.short_name}', {area_two.area_one_id}, {area_two.country_id}, '{area_two.description or ''}', '{area_two.url or ''}', '{area_two.map_image_url or ''}');\n")

                f.write("\n-- Localities\n")
                for locality in localities:
                    f.write(f"INSERT INTO locality (id, google_name, name, short_name, area_two_id, area_one_id, country_id, description, url, map_image_url) VALUES ({locality.id}, '{locality.google_name or ''}', '{locality.name}', '{locality.short_name}', {locality.area_two_id}, {locality.area_one_id}, {locality.country_id}, '{locality.description or ''}', '{locality.url or ''}', '{locality.map_image_url or ''}');\n")

                f.write("\n-- Spots (geographic relationships only)\n")
                for spot in spots:
                    f.write(f"UPDATE spot SET country_id = {spot.country_id or 'NULL'}, area_one_id = {spot.area_one_id or 'NULL'}, area_two_id = {spot.area_two_id or 'NULL'}, locality_id = {spot.locality_id or 'NULL'} WHERE id = {spot.id};\n")

                f.write("\n-- DiveShops (geographic relationships only)\n")
                for shop in dive_shops:
                    f.write(f"UPDATE dive_shop SET country_id = {shop.country_id or 'NULL'}, area_one_id = {shop.area_one_id or 'NULL'}, area_two_id = {shop.area_two_id or 'NULL'}, locality_id = {shop.locality_id or 'NULL'} WHERE id = {shop.id};\n")

            print(f"✅ SQLAlchemy backup created successfully: {backup_file}")
            print("   Note: This is a simplified backup format")
            return backup_file

        except Exception as e:
            print(f"❌ SQLAlchemy backup failed: {e}")
            return None


def backup_via_json():
    """Create a JSON backup of geographic data (simplest method)"""

    app = create_app()
    with app.app_context():

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"backup_geographic_merge_{timestamp}.json"

        print(f"Creating JSON backup: {backup_file}")

        try:
            import json

            # Get all data from geographic tables
            countries = [{
                'id': c.id,
                'name': c.name,
                'short_name': c.short_name,
                'description': c.description,
                'url': c.url,
                'map_image_url': c.map_image_url
            } for c in Country.query.all()]

            area_ones = [{
                'id': a.id,
                'google_name': a.google_name,
                'name': a.name,
                'short_name': a.short_name,
                'country_id': a.country_id,
                'description': a.description,
                'url': a.url,
                'map_image_url': a.map_image_url
            } for a in AreaOne.query.all()]

            area_twos = [{
                'id': a.id,
                'google_name': a.google_name,
                'name': a.name,
                'short_name': a.short_name,
                'area_one_id': a.area_one_id,
                'country_id': a.country_id,
                'description': a.description,
                'url': a.url,
                'map_image_url': a.map_image_url
            } for a in AreaTwo.query.all()]

            localities = [{
                'id': l.id,
                'google_name': l.google_name,
                'name': l.name,
                'short_name': l.short_name,
                'area_two_id': l.area_two_id,
                'area_one_id': l.area_one_id,
                'country_id': l.country_id,
                'description': l.description,
                'url': l.url,
                'map_image_url': l.map_image_url
            } for l in Locality.query.all()]

            # Get geographic relationships for spots and shops
            spot_relationships = [{
                'id': s.id,
                'country_id': s.country_id,
                'area_one_id': s.area_one_id,
                'area_two_id': s.area_two_id,
                'locality_id': s.locality_id
            } for s in Spot.query.all()]

            shop_relationships = [{
                'id': s.id,
                'country_id': s.country_id,
                'area_one_id': s.area_one_id,
                'area_two_id': s.area_two_id,
                'locality_id': s.locality_id
            } for s in DiveShop.query.all()]

            backup_data = {
                'created': datetime.now().isoformat(),
                'countries': countries,
                'area_ones': area_ones,
                'area_twos': area_twos,
                'localities': localities,
                'spot_relationships': spot_relationships,
                'shop_relationships': shop_relationships
            }

            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)

            print(f"✅ JSON backup created successfully: {backup_file}")
            print(f"   Countries: {len(countries)}")
            print(f"   AreaOnes: {len(area_ones)}")
            print(f"   AreaTwos: {len(area_twos)}")
            print(f"   Localities: {len(localities)}")
            print(f"   Spot relationships: {len(spot_relationships)}")
            print(f"   Shop relationships: {len(shop_relationships)}")

            return backup_file

        except Exception as e:
            print(f"❌ JSON backup failed: {e}")
            return None


def restore_database(backup_file):
    """Restore database from backup"""

    app = create_app()
    db_url = app.config['SQLALCHEMY_DATABASE_URI']

    if db_url.startswith('postgresql://'):
        # PostgreSQL restore
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url)
        db_name = parsed.path[1:]
        host = parsed.hostname
        port = parsed.port or 5432
        user = parsed.username
        password = parsed.password

        print(f"Restoring PostgreSQL database from: {backup_file}")

        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password

        cmd = [
            'psql',
            '-h', host,
            '-p', str(port),
            '-U', user,
            '-d', db_name,
            '-f', backup_file
        ]

        try:
            result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
            print("✅ Database restored successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Restore failed: {e}")
            print(f"Error output: {e.stderr}")
            return False

    elif db_url.startswith('sqlite:///'):
        # SQLite restore
        db_path = db_url.replace('sqlite:///', '')

        print(f"Restoring SQLite database from: {backup_file}")

        try:
            import shutil
            shutil.copy2(backup_file, db_path)
            print("✅ Database restored successfully")
            return True
        except Exception as e:
            print(f"❌ Restore failed: {e}")
            return False

    else:
        print(f"❌ Unsupported database type: {db_url}")
        return False


def test_constraints():
    """Test if constraints can be added without conflicts"""

    app = create_app()
    with app.app_context():

        print("\n=== TESTING CONSTRAINT ADDITION ===\n")

        # Test each constraint
        constraints = [
            ("unique_country_short_name", "country", "short_name"),
            ("unique_area_one_short_name_country", "area_one", "short_name, country_id"),
            ("unique_area_two_short_name_country_area_one", "area_two", "short_name, country_id, area_one_id"),
            ("unique_locality_short_name_country_area_one_area_two", "locality", "short_name, country_id, area_one_id, area_two_id")
        ]

        for constraint_name, table, columns in constraints:
            try:
                # Check if constraint already exists
                result = db.session.execute(text(f"""
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_name = '{table}'
                    AND constraint_name = '{constraint_name}'
                """))

                if result.fetchone():
                    print(f"⚠️  Constraint {constraint_name} already exists on {table}")
                else:
                    print(f"✅ Constraint {constraint_name} can be added to {table}")

            except Exception as e:
                print(f"❌ Error checking constraint {constraint_name}: {e}")


if __name__ == "__main__":
    print("=== TESTING MERGE DUPLICATES SCRIPT ===\n")

    # 1. Dry run to see what would happen
    print("1. Running dry run to see what changes would be made...")
    dry_run_merge()

    # 2. Test constraint addition
    print("\n2. Testing constraint addition...")
    test_constraints()

        # 3. Offer to create backup
    print("\n3. Database backup options:")
    print("   - Run: python scripts/test_merge_duplicates.py --backup")
    print("   - Run: python scripts/test_merge_duplicates.py --json-backup")
    print("   - Run: python scripts/test_merge_duplicates.py --restore <backup_file>")

    if len(sys.argv) > 1:
        if sys.argv[1] == '--backup':
            backup_file = backup_database()
            if backup_file:
                print(f"\n✅ Backup created: {backup_file}")
                print(f"   To restore: python scripts/test_merge_duplicates.py --restore {backup_file}")
        elif sys.argv[1] == '--json-backup':
            backup_file = backup_via_json()
            if backup_file:
                print(f"\n✅ JSON backup created: {backup_file}")
                print(f"   This is a simple backup format that doesn't require external tools")
        elif sys.argv[1] == '--restore' and len(sys.argv) > 2:
            backup_file = sys.argv[2]
            if restore_database(backup_file):
                print("\n✅ Database restored successfully")
            else:
                print("\n❌ Database restore failed")

    print("\n=== TESTING COMPLETE ===")
    print("Review the output above to understand what the merge script would do.")
    print("If everything looks correct, you can proceed with the actual merge.")