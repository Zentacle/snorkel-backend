#!/usr/bin/env python3
"""
Script to test and benchmark geographic endpoint performance
"""

import os
import sys
import time

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app import create_app, db
from app.models import DiveShop, GeographicNode, Spot
from app.routes.geography import get_descendant_node_ids


def benchmark_descendant_queries():
    """Benchmark the old vs new descendant query methods"""

    app = create_app()
    with app.app_context():

        print("Benchmarking descendant query methods...")
        print("=" * 50)

        # Get a few test nodes at different levels
        test_nodes = GeographicNode.query.limit(5).all()

        for node in test_nodes:
            print(f"\nTesting node: {node.name} (ID: {node.id})")

            # Test old method (recursive Python)
            start_time = time.time()
            old_descendants = [node.id] + [desc.id for desc in node.get_descendants()]
            old_time = time.time() - start_time

            # Test new method (CTE)
            start_time = time.time()
            new_descendants = get_descendant_node_ids(node.id)
            new_time = time.time() - start_time

            print(
                f"  Old method: {len(old_descendants)} descendants in {old_time:.4f}s"
            )
            print(
                f"  New method: {len(new_descendants)} descendants in {new_time:.4f}s"
            )
            print(f"  Speedup: {old_time/new_time:.2f}x")

            # Verify results match
            if set(old_descendants) == set(new_descendants):
                print(f"  ✓ Results match")
            else:
                print(f"  ⚠ Results differ!")


def benchmark_spot_queries():
    """Benchmark spot query performance"""

    app = create_app()
    with app.app_context():

        print("\nBenchmarking spot query performance...")
        print("=" * 50)

        # Get a country-level node (highest hierarchy level)
        country_node = GeographicNode.query.filter_by(admin_level=0).first()
        if not country_node:
            print("No country-level nodes found")
            return

        print(f"Testing with country: {country_node.name}")

        # Get descendant IDs
        descendant_ids = get_descendant_node_ids(country_node.id)
        print(f"Total descendant nodes: {len(descendant_ids)}")

        # Test different query approaches
        queries = [
            (
                "Basic query",
                lambda: Spot.query.filter(
                    Spot.geographic_node_id.in_(descendant_ids)
                ).count(),
            ),
            (
                "With filters",
                lambda: Spot.query.filter(
                    Spot.geographic_node_id.in_(descendant_ids),
                    Spot.is_verified.isnot(False),
                    Spot.is_deleted.isnot(True),
                ).count(),
            ),
            (
                "With sorting",
                lambda: Spot.query.filter(
                    Spot.geographic_node_id.in_(descendant_ids),
                    Spot.is_verified.isnot(False),
                    Spot.is_deleted.isnot(True),
                )
                .order_by(Spot.num_reviews.desc())
                .limit(50)
                .all(),
            ),
            (
                "With eager loading",
                lambda: Spot.query.filter(
                    Spot.geographic_node_id.in_(descendant_ids),
                    Spot.is_verified.isnot(False),
                    Spot.is_deleted.isnot(True),
                )
                .options(
                    db.joinedload(Spot.geographic_node), db.joinedload(Spot.reviews)
                )
                .order_by(Spot.num_reviews.desc())
                .limit(50)
                .all(),
            ),
        ]

        for name, query_func in queries:
            start_time = time.time()
            result = query_func()
            query_time = time.time() - start_time

            if isinstance(result, list):
                print(f"  {name}: {len(result)} results in {query_time:.4f}s")
            else:
                print(f"  {name}: {result} results in {query_time:.4f}s")


def benchmark_dive_shop_queries():
    """Benchmark dive shop query performance"""

    app = create_app()
    with app.app_context():

        print("\nBenchmarking dive shop query performance...")
        print("=" * 50)

        # Get a country-level node
        country_node = GeographicNode.query.filter_by(admin_level=0).first()
        if not country_node:
            print("No country-level nodes found")
            return

        print(f"Testing with country: {country_node.name}")

        # Get descendant IDs
        descendant_ids = get_descendant_node_ids(country_node.id)

        # Test different query approaches
        queries = [
            (
                "Basic query",
                lambda: DiveShop.query.filter(
                    DiveShop.geographic_node_id.in_(descendant_ids)
                ).count(),
            ),
            (
                "With sorting",
                lambda: DiveShop.query.filter(
                    DiveShop.geographic_node_id.in_(descendant_ids)
                )
                .order_by(DiveShop.rating.desc())
                .limit(50)
                .all(),
            ),
            (
                "With eager loading",
                lambda: DiveShop.query.filter(
                    DiveShop.geographic_node_id.in_(descendant_ids)
                )
                .options(
                    db.joinedload(DiveShop.geographic_node),
                    db.joinedload(DiveShop.reviews),
                )
                .order_by(DiveShop.rating.desc())
                .limit(50)
                .all(),
            ),
        ]

        for name, query_func in queries:
            start_time = time.time()
            result = query_func()
            query_time = time.time() - start_time

            if isinstance(result, list):
                print(f"  {name}: {len(result)} results in {query_time:.4f}s")
            else:
                print(f"  {name}: {result} results in {query_time:.4f}s")


def check_index_usage():
    """Check if indexes are being used effectively"""

    app = create_app()
    with app.app_context():

        print("\nChecking index usage...")
        print("=" * 50)

        # Check if indexes exist
        indexes_to_check = [
            ("geographic_node", "ix_geographic_node_parent_id"),
            ("geographic_node", "ix_geographic_node_admin_level"),
            ("spot", "ix_spot_geographic_node_id"),
            ("dive_shop", "ix_dive_shop_geographic_node_id"),
        ]

        for table, index_name in indexes_to_check:
            try:
                # This is a simplified check - in production you'd use EXPLAIN ANALYZE
                result = db.session.execute(
                    f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'"
                )
                exists = result.fetchone() is not None
                print(f"  {index_name}: {'✓' if exists else '✗'}")
            except Exception as e:
                print(f"  {index_name}: Error checking - {e}")


def main():
    """Run all performance tests"""

    print("Geographic Endpoint Performance Test")
    print("=" * 40)

    # Run benchmarks
    benchmark_descendant_queries()
    benchmark_spot_queries()
    benchmark_dive_shop_queries()
    check_index_usage()

    print("\nPerformance test completed!")


if __name__ == "__main__":
    main()
