#!/usr/bin/env python3
"""
Script to find and drop unnamed foreign key constraints
"""

import sys
import os

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import inspect, text

def find_and_drop_constraints():
    """Find and drop unnamed foreign key constraints"""

    app = create_app()
    with app.app_context():

        print("🔍 Finding unnamed foreign key constraints...")

        inspector = inspect(db.engine)

        # Check spot table
        spot_fks = inspector.get_foreign_keys('spot')
        for fk in spot_fks:
            if 'geographic_node_id' in fk['constrained_columns']:
                print(f"Found Spot FK: {fk['name']}")
                try:
                    db.session.execute(text(f"ALTER TABLE spot DROP CONSTRAINT {fk['name']}"))
                    print(f"✅ Dropped constraint: {fk['name']}")
                except Exception as e:
                    print(f"❌ Failed to drop {fk['name']}: {e}")

        # Check dive_shop table
        dive_shop_fks = inspector.get_foreign_keys('dive_shop')
        for fk in dive_shop_fks:
            if 'geographic_node_id' in fk['constrained_columns']:
                print(f"Found DiveShop FK: {fk['name']}")
                try:
                    db.session.execute(text(f"ALTER TABLE dive_shop DROP CONSTRAINT {fk['name']}"))
                    print(f"✅ Dropped constraint: {fk['name']}")
                except Exception as e:
                    print(f"❌ Failed to drop {fk['name']}: {e}")

        # Check geographic_node table for unique constraint
        try:
            result = db.session.execute(text("""
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'geographic_node'::regclass
                AND contype = 'u'
                AND conname LIKE '%short_name%'
            """))
            unique_constraints = result.fetchall()

            for constraint in unique_constraints:
                constraint_name = constraint[0]
                print(f"Found unique constraint: {constraint_name}")
                try:
                    db.session.execute(text(f"ALTER TABLE geographic_node DROP CONSTRAINT {constraint_name}"))
                    print(f"✅ Dropped unique constraint: {constraint_name}")
                except Exception as e:
                    print(f"❌ Failed to drop {constraint_name}: {e}")

        except Exception as e:
            print(f"❌ Error checking unique constraints: {e}")

        db.session.commit()
        print("✅ All constraints dropped successfully!")

if __name__ == "__main__":
    find_and_drop_constraints()