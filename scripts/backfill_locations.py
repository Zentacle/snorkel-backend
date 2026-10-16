#!/usr/bin/env python3
"""
Give spots and shops that have coordinates but no location one: first by
copying the nearest located spot/shop (free), then optionally by Google
reverse geocoding. See app/helpers/location_backfill.py.

Dry run by default (everything rolled back). Google is only called with
--google, and costs money even in a dry run, so try it with --limit first:

    python scripts/backfill_locations.py                     # free: nearby matches + cost estimate
    python scripts/backfill_locations.py --google --limit 20 # sample Google results, nothing written
    python scripts/backfill_locations.py --google --apply    # write

Options: --spots / --shops (default both), --max-km N (default 15).
Afterwards, run scripts/build_places.py to attach the new locations to places.
"""

import argparse
import os
import sys

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.helpers.location_backfill import backfill_locations
from app.models import DiveShop, Spot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--google", action="store_true", help="reverse geocode items with no nearby match")
    parser.add_argument("--limit", type=int, help="only process the first N items of each type")
    parser.add_argument("--max-km", type=float, default=15.0, help="max distance for a nearby match")
    parser.add_argument("--spots", action="store_true")
    parser.add_argument("--shops", action="store_true")
    args = parser.parse_args()
    models = [m for m, flag in ((Spot, args.spots), (DiveShop, args.shops)) if flag] or [Spot, DiveShop]

    app = create_app()
    with app.app_context():
        for model in models:
            report = backfill_locations(
                model, apply=args.apply, use_google=args.google, limit=args.limit, max_km=args.max_km
            )
            print(f"\n== {report['model']}")
            for key in ("targets", "nearby", "google", "needs_google", "skipped_no_coordinates"):
                print(f"{key}: {report.get(key, 0)}")
            if report["needs_google"]:
                print(f"estimated Google cost for the rest: ${report['estimated_google_cost_usd']}")
            if report["google_statuses"]:
                print(f"google statuses: {report['google_statuses']}")
            print(f"unresolved: {len(report['unresolved_ids'])} {report['unresolved_ids'][:30]}")
            print(f"failed (skipped, see reason): {len(report['failed'])}")
            for item_id, reason in report["failed"][:30]:
                print(f"  {item_id}: {reason}")
            for sample in report["samples"]:
                print(f"  {sample}")
    print("\nApplied." if args.apply else "\nDry run, nothing written. Pass --apply to write.")


if __name__ == "__main__":
    main()
