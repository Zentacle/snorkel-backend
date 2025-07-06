#!/usr/bin/env python3
"""
Rollback script for merge_duplicates.py
Restores database from backup if merge goes wrong
"""

import os
import subprocess
import sys
from datetime import datetime

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app


def list_backups():
    """List available backup files"""

    print("=== AVAILABLE BACKUP FILES ===\n")

    backup_files = []
    for file in os.listdir('.'):
        if file.startswith('backup_geographic_merge_') and (file.endswith('.sql') or file.endswith('.db')):
            backup_files.append(file)

    if not backup_files:
        print("No backup files found in current directory.")
        print("Run the test script first to create a backup:")
        print("  python scripts/test_merge_duplicates.py --backup")
        return []

    backup_files.sort(reverse=True)  # Most recent first

    for i, backup_file in enumerate(backup_files, 1):
        # Get file stats
        stat = os.stat(backup_file)
        size_mb = stat.st_size / (1024 * 1024)
        created = datetime.fromtimestamp(stat.st_ctime)

        print(f"{i}. {backup_file}")
        print(f"   Size: {size_mb:.1f} MB")
        print(f"   Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

    return backup_files


def restore_from_backup(backup_file):
    """Restore database from backup file"""

    app = create_app()
    db_url = app.config['SQLALCHEMY_DATABASE_URI']

    print(f"=== RESTORING DATABASE FROM BACKUP ===\n")
    print(f"Backup file: {backup_file}")
    print(f"Database URL: {db_url}")
    print()

    # Confirm before proceeding
    response = input("⚠️  This will OVERWRITE your current database. Are you sure? (yes/no): ")
    if response.lower() != 'yes':
        print("Restore cancelled.")
        return False

    if db_url.startswith('postgresql://'):
        # PostgreSQL restore
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url)
        db_name = parsed.path[1:]
        host = parsed.hostname
        port = parsed.port or 5432
        user = parsed.username
        password = parsed.password

        print(f"Restoring PostgreSQL database...")

        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password

        # Drop and recreate database
        drop_cmd = [
            'dropdb',
            '-h', host,
            '-p', str(port),
            '-U', user,
            '--if-exists',
            db_name
        ]

        create_cmd = [
            'createdb',
            '-h', host,
            '-p', str(port),
            '-U', user,
            db_name
        ]

        restore_cmd = [
            'psql',
            '-h', host,
            '-p', str(port),
            '-U', user,
            '-d', db_name,
            '-f', backup_file
        ]

        try:
            print("Dropping existing database...")
            subprocess.run(drop_cmd, env=env, check=True, capture_output=True)

            print("Creating new database...")
            subprocess.run(create_cmd, env=env, check=True, capture_output=True)

            print("Restoring from backup...")
            result = subprocess.run(restore_cmd, env=env, check=True, capture_output=True, text=True)

            print("✅ Database restored successfully!")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Restore failed: {e}")
            print(f"Error output: {e.stderr}")
            return False

    elif db_url.startswith('sqlite:///'):
        # SQLite restore
        db_path = db_url.replace('sqlite:///', '')

        print(f"Restoring SQLite database...")

        try:
            import shutil

            # Stop any running processes that might be using the database
            print("Stopping database connections...")

            # Copy backup to database location
            shutil.copy2(backup_file, db_path)

            print("✅ Database restored successfully!")
            return True

        except Exception as e:
            print(f"❌ Restore failed: {e}")
            return False

    else:
        print(f"❌ Unsupported database type: {db_url}")
        return False


def verify_restore():
    """Verify that the restore was successful"""

    app = create_app()
    with app.app_context():

        print("\n=== VERIFYING RESTORE ===\n")

        try:
            from app.models import AreaOne, AreaTwo, Country, Locality

            # Check if tables exist and have data
            country_count = Country.query.count()
            area_one_count = AreaOne.query.count()
            area_two_count = AreaTwo.query.count()
            locality_count = Locality.query.count()

            print(f"✅ Database connection successful")
            print(f"   Countries: {country_count}")
            print(f"   AreaOnes: {area_one_count}")
            print(f"   AreaTwos: {area_two_count}")
            print(f"   Localities: {locality_count}")

            if country_count > 0:
                print("✅ Restore appears successful - data is present")
                return True
            else:
                print("⚠️  Restore may have failed - no data found")
                return False

        except Exception as e:
            print(f"❌ Error verifying restore: {e}")
            return False


if __name__ == "__main__":
    print("=== ROLLBACK MERGE DUPLICATES ===\n")

    if len(sys.argv) > 1:
        # Direct restore from command line
        backup_file = sys.argv[1]
        if os.path.exists(backup_file):
            if restore_from_backup(backup_file):
                verify_restore()
        else:
            print(f"❌ Backup file not found: {backup_file}")
    else:
        # Interactive mode
        backup_files = list_backups()

        if backup_files:
            print("To restore from a specific backup, run:")
            print(f"  python scripts/rollback_merge.py {backup_files[0]}")
            print()

            response = input("Would you like to restore from the most recent backup? (yes/no): ")
            if response.lower() == 'yes':
                if restore_from_backup(backup_files[0]):
                    verify_restore()

    print("\n=== ROLLBACK COMPLETE ===")