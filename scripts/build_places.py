#!/usr/bin/env python3
"""
Build the Place tree from the legacy Country/AreaOne/AreaTwo/Locality tables
and point every spot and shop at its place.

Dry run by default (everything is rolled back); pass --apply to write.
Safe to re-run. See LOCATION_MIGRATION.md.
"""

import os
import sys

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.helpers.places import build_places_from_legacy

PROBLEMS = ("no_country", "no_url", "duplicate_path", "duplicate_slug")


def main():
    apply = "--apply" in sys.argv
    app = create_app()
    with app.app_context():
        report = build_places_from_legacy(apply=apply)

    for key in ("created", "updated", "moved", "spots_assigned", "spots_unplaced", "shops_assigned", "shops_unplaced"):
        print(f"{key}: {report.get(key, 0)}")
    for key in PROBLEMS:
        rows = report[key]
        print(f"{key}: {len(rows)}")
        for row in rows[:25]:
            print(f"  {row}")
    print("Applied." if report["applied"] else "Dry run, nothing written. Pass --apply to write.")


if __name__ == "__main__":
    main()
