#!/usr/bin/env python3
"""
Store each geographic node's current public URL in GeographicNode.path.

Dry run by default; pass --apply to write. Run after
migrate_geographic_hierarchy_fast.py (see LOCATION_MIGRATION.md, step 2).
"""

import os
import sys

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.helpers.geographic_paths import backfill_node_paths


def main():
    apply = "--apply" in sys.argv
    app = create_app()
    with app.app_context():
        report = backfill_node_paths(apply=apply)

    print(f"Nodes without a path: {report['nodes_without_path']}")
    print(f"Paths found from legacy rows: {report['planned']}")
    print(f"Nodes with no legacy URL: {len(report['no_legacy_url'])} {report['no_legacy_url'][:20]}")
    if report["duplicate_paths"]:
        print(f"DUPLICATE PATHS ({len(report['duplicate_paths'])}), nothing written:")
        for path, ids in list(report["duplicate_paths"].items())[:50]:
            print(f"  {path}: nodes {ids}")
    print("Applied." if report["applied"] else "Dry run, nothing written. Pass --apply to write.")
    return 1 if report["duplicate_paths"] else 0


if __name__ == "__main__":
    sys.exit(main())
