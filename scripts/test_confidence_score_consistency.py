#!/usr/bin/env python3
"""
Script to test confidence score calculation consistency between Python and database
"""

import os
import sys

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app import create_app, db
from app.models import Spot


def test_confidence_score_consistency():
    """Test that Python and database confidence score calculations match"""

    app = create_app()
    with app.app_context():

        print("Testing confidence score calculation consistency...")
        print("=" * 60)

        # Get a sample of spots with different review counts and ratings
        test_spots = (
            Spot.query.filter(Spot.num_reviews > 0, Spot.rating.isnot(None))
            .limit(20)
            .all()
        )

        if not test_spots:
            print("No spots found with reviews and ratings")
            return

        print(f"Testing {len(test_spots)} spots...")
        print()

        all_match = True

        for i, spot in enumerate(test_spots):
            # Python calculation
            python_score = spot.get_confidence_score()

            # Database calculation
            db_result = (
                db.session.query(Spot.get_confidence_score)
                .filter_by(id=spot.id)
                .scalar()
            )
            db_score = float(db_result) if db_result is not None else 0.0

            # Compare results
            match = (
                abs(python_score - db_score) < 0.001
            )  # Allow small floating point differences

            status = "✓" if match else "✗"
            print(f"{status} Spot {i+1}: {spot.name}")
            print(f"    Rating: {spot.rating}, Reviews: {spot.num_reviews}")
            print(f"    Python score: {python_score:.6f}")
            print(f"    DB score:     {db_score:.6f}")
            print(f"    Difference:   {abs(python_score - db_score):.6f}")
            print()

            if not match:
                all_match = False

        # Test edge cases
        print("Testing edge cases...")
        print()

        # Test spots with no reviews
        no_review_spots = Spot.query.filter(Spot.num_reviews == 0).limit(5).all()

        for spot in no_review_spots:
            python_score = spot.get_confidence_score()
            db_result = (
                db.session.query(Spot.get_confidence_score)
                .filter_by(id=spot.id)
                .scalar()
            )
            db_score = float(db_result) if db_result is not None else 0.0

            match = abs(python_score - db_score) < 0.001
            status = "✓" if match else "✗"
            print(
                f"{status} No reviews: {spot.name} - Python: {python_score}, DB: {db_score}"
            )

        print()

        if all_match:
            print("✓ All confidence score calculations match!")
        else:
            print("✗ Some confidence score calculations differ!")
            print("   This indicates an issue with the database expression.")


def test_sorting_consistency():
    """Test that sorting by confidence score produces the same results"""

    app = create_app()
    with app.app_context():

        print("\nTesting sorting consistency...")
        print("=" * 40)

        # Get a geographic node to test with
        test_node = (
            db.session.query(Spot.geographic_node_id)
            .filter(Spot.geographic_node_id.isnot(None))
            .first()
        )

        if not test_node:
            print("No spots with geographic nodes found")
            return

        node_id = test_node[0]

        # Get spots for this node
        spots = Spot.query.filter(
            Spot.geographic_node_id == node_id,
            Spot.is_verified.isnot(False),
            Spot.is_deleted.isnot(True),
        ).all()

        if len(spots) < 2:
            print("Not enough spots to test sorting")
            return

        print(f"Testing sorting with {len(spots)} spots...")

        # Python-side sorting (original method)
        python_sorted = sorted(
            spots, key=lambda s: s.get_confidence_score(), reverse=True
        )
        python_order = [s.id for s in python_sorted[:10]]  # Top 10

        # Database-side sorting (new method)
        db_sorted = (
            Spot.query.filter(
                Spot.geographic_node_id == node_id,
                Spot.is_verified.isnot(False),
                Spot.is_deleted.isnot(True),
            )
            .order_by(Spot.get_confidence_score.desc())
            .limit(10)
            .all()
        )
        db_order = [s.id for s in db_sorted]

        # Compare orders
        match = python_order == db_order

        print(f"Python order: {python_order}")
        print(f"DB order:     {db_order}")
        print(f"Match: {'✓' if match else '✗'}")

        if not match:
            print("\nDetailed comparison:")
            for i, (py_id, db_id) in enumerate(zip(python_order, db_order)):
                py_spot = next(s for s in python_sorted if s.id == py_id)
                db_spot = next(s for s in db_sorted if s.id == db_id)
                print(
                    f"  {i+1}: Python {py_id} (score: {py_spot.get_confidence_score():.6f}) vs DB {db_id} (score: {db_spot.get_confidence_score():.6f})"
                )


def main():
    """Run all consistency tests"""

    print("Confidence Score Consistency Test")
    print("=" * 40)

    test_confidence_score_consistency()
    test_sorting_consistency()

    print("\nConsistency test completed!")


if __name__ == "__main__":
    main()
