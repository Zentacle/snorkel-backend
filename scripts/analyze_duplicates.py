#!/usr/bin/env python3
"""
Script to analyze duplicate data in the original geographic tables
Helps understand the scope of duplicate data before migration
"""

import os
import sys

from sqlalchemy import func

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import AreaOne, AreaTwo, Country, Locality, Spot


def analyze_duplicates():
    """Analyze duplicate data in the original geographic tables"""

    app = create_app()
    with app.app_context():

        print("=== ANALYZING DUPLICATE DATA IN ORIGINAL TABLES ===\n")

        # Analyze Country duplicates
        print("1. COUNTRY DUPLICATES:")
        country_duplicates = db.session.query(
            Country.short_name,
            func.count(Country.id).label('count')
        ).group_by(Country.short_name).having(
            func.count(Country.id) > 1
        ).all()

        if country_duplicates:
            print(f"   Found {len(country_duplicates)} duplicate short_names:")
            for short_name, count in country_duplicates:
                countries = Country.query.filter_by(short_name=short_name).all()
                print(f"     '{short_name}': {count} records")
                for country in countries:
                    spot_count = Spot.query.filter_by(country_id=country.id).count()
                    print(f"       ID: {country.id}, name: '{country.name}', spots: {spot_count}")
        else:
            print("   No duplicate countries found")

        print()

        # Analyze AreaOne duplicates
        print("2. AREA_ONE DUPLICATES:")
        area_one_duplicates = db.session.query(
            AreaOne.short_name,
            AreaOne.country_id,
            func.count(AreaOne.id).label('count')
        ).group_by(AreaOne.short_name, AreaOne.country_id).having(
            func.count(AreaOne.id) > 1
        ).all()

        if area_one_duplicates:
            print(f"   Found {len(area_one_duplicates)} duplicate (short_name, country_id) combinations:")
            for short_name, country_id, count in area_one_duplicates:
                country = Country.query.get(country_id)
                country_name = country.name if country else f"Unknown (ID: {country_id})"
                area_ones = AreaOne.query.filter_by(short_name=short_name, country_id=country_id).all()
                print(f"     '{short_name}' in '{country_name}': {count} records")
                for area_one in area_ones:
                    spot_count = Spot.query.filter_by(area_one_id=area_one.id).count()
                    print(f"       ID: {area_one.id}, name: '{area_one.name}', spots: {spot_count}")
        else:
            print("   No duplicate area_ones found")

        print()

        # Analyze AreaTwo duplicates
        print("3. AREA_TWO DUPLICATES:")
        area_two_duplicates = db.session.query(
            AreaTwo.short_name,
            AreaTwo.country_id,
            AreaTwo.area_one_id,
            func.count(AreaTwo.id).label('count')
        ).group_by(AreaTwo.short_name, AreaTwo.country_id, AreaTwo.area_one_id).having(
            func.count(AreaTwo.id) > 1
        ).all()

        if area_two_duplicates:
            print(f"   Found {len(area_two_duplicates)} duplicate (short_name, country_id, area_one_id) combinations:")
            for short_name, country_id, area_one_id, count in area_two_duplicates:
                country = Country.query.get(country_id)
                area_one = AreaOne.query.get(area_one_id)
                country_name = country.name if country else f"Unknown (ID: {country_id})"
                area_one_name = area_one.name if area_one else f"Unknown (ID: {area_one_id})"
                area_twos = AreaTwo.query.filter_by(short_name=short_name, country_id=country_id, area_one_id=area_one_id).all()
                print(f"     '{short_name}' in '{country_name}'/'{area_one_name}': {count} records")
                for area_two in area_twos:
                    spot_count = Spot.query.filter_by(area_two_id=area_two.id).count()
                    print(f"       ID: {area_two.id}, name: '{area_two.name}', spots: {spot_count}")
        else:
            print("   No duplicate area_twos found")

        print()

        # Analyze Locality duplicates
        print("4. LOCALITY DUPLICATES:")
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
            print(f"   Found {len(locality_duplicates)} duplicate (short_name, country_id, area_one_id, area_two_id) combinations:")
            for short_name, country_id, area_one_id, area_two_id, count in locality_duplicates:
                country = Country.query.get(country_id)
                area_one = AreaOne.query.get(area_one_id)
                area_two = AreaTwo.query.get(area_two_id)
                country_name = country.name if country else f"Unknown (ID: {country_id})"
                area_one_name = area_one.name if area_one else f"Unknown (ID: {area_one_id})"
                area_two_name = area_two.name if area_two else f"Unknown (ID: {area_two_id})"
                localities = Locality.query.filter_by(short_name=short_name, country_id=country_id, area_one_id=area_one_id, area_two_id=area_two_id).all()
                print(f"     '{short_name}' in '{country_name}'/'{area_one_name}'/'{area_two_name}': {count} records")
                for locality in localities:
                    spot_count = Spot.query.filter_by(locality_id=locality.id).count()
                    print(f"       ID: {locality.id}, name: '{locality.name}', spots: {spot_count}")
        else:
            print("   No duplicate localities found")

        print()

        # Summary
        print("=== SUMMARY ===")
        total_duplicates = len(country_duplicates) + len(area_one_duplicates) + len(area_two_duplicates) + len(locality_duplicates)
        print(f"Total duplicate groups found: {total_duplicates}")

        if total_duplicates > 0:
            print("\n⚠️  Duplicate data detected! Migration script should handle these gracefully.")
            print("   Check the spot counts above to identify duplicates with no meaningful relationships.")
        else:
            print("\n✅ No duplicate data detected. Migration should proceed smoothly.")

if __name__ == "__main__":
    analyze_duplicates()