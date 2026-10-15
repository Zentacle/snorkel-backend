# Location hierarchy migration: design doc

Status: **Step 1 in review**, Oct 2026
Owner: Mayank

## Summary

Replace the four fixed location tables (`Country` → `AreaOne` → `AreaTwo` → `Locality`) with a single tree of **`Place`**s that can be any depth. **Every public URL stays exactly the same.** Spot URLs remain `/Beach/<id>/<slug>`, and location URLs keep their current form, `_` segments included.

`Place` is new and replaces `GeographicNode`, an earlier attempt from July 2025 that was never switched on and had structural problems (see "Why not GeographicNode").

## Why change the location model

The fixed hierarchy doesn't match real geography, and that has costs we can measure:

1. **Gaps drop out of lists.** Places with no state or county get a `_` in the URL (`/loc/pt/beja/_/vila-nova-de-milfontes`). The location list endpoints (`/locality/*`) inner-join the full chain, so these pages are missing from the sitemaps and directories. 42 of them earned 522 search clicks anyway.
2. **Every query special-cases the levels**: four tables plus `_` wildcards, in `/spots/get`, `/locality/*`, the sitemaps and `/locality/stats`.
3. **Geographies that matter for SEO can't be represented**: islands, atolls, marine parks, and regions that cross borders (Florida Keys, Red Sea). The roadmap's "best places to snorkel in X" guides need them.

## Why URLs must not change

- Location pages earn **59% of search clicks** (Search Console, Jun 2025 – Oct 2026), across 4,868 URLs.
- Google doesn't penalize a `_` in a path. `/_/` pages rank today.
- Changing thousands of URLs, even with 301s, usually costs rankings for weeks or months. Doing it before the March–August season would risk the peak for nothing.

**URL policy:** a URL that exists today keeps working, unchanged, as the canonical URL. New places (islands, regions) get new URLs, which only adds pages. Renaming an existing URL needs a 301 and a written reason.

## The `Place` model

```
place
  id, parent_id → place.id (null for countries)
  kind         country | region | county | city | island | atoll | marine_park | body_of_water | area
  name, slug   slug unique per parent        (uq_place_parent_slug)
  path         public URL, stored, unique    (uq_place_path)    e.g. /loc/pt/beja/_/vila-nova
  lineage      ancestor ids incl. self       e.g. /1/5/23/      (indexed, text_pattern_ops)
  depth        0 for countries
  country_code, google_name, google_place_id, latitude, longitude, description, map_image_url
  legacy_type, legacy_id                     (uq_place_legacy) the legacy row it was built from
  created, updated

spot.place_id, dive_shop.place_id → place.id (the most specific place)
```

Design choices:

- **`path` is stored, never derived from the tree.** The tree can be reshaped (moving a town under a new island, filling a gap) without touching any URL. This is what makes the URL policy enforceable.
- **`lineage` is a materialized path of ids.** "Everything inside Hawaii" is one indexed prefix query (`lineage LIKE '/1/5/%'`), with no recursion. It's portable (SQLite in tests, Postgres in production), and `Place.move_to()` rewrites a subtree's lineage in one pass.
- **`kind` replaces `admin_level`.** Depth and type are independent: an island can sit under a region or directly under a country.
- **One legacy link per place.** `(legacy_type, legacy_id)` replaces four nullable legacy foreign keys. It makes the builder idempotent, and it's dropped with the legacy tables at the end.
- **Spots and shops point at the most specific place.** Ancestors are implied by `lineage`.
- **Not built yet (step 5):** "also in" links for regions that overlap the tree (Florida Keys within Florida; the Red Sea across countries), and a redirects table for the rare deliberate URL change.

## Why not GeographicNode

`GeographicNode` (July 2025) was dropped rather than fixed:

| Problem | Effect |
|---|---|
| `Spot.get_url()` switched to `/loc/.../<slug>-<id>` once a spot had a node | Running its migration script would have changed every dive site URL |
| URLs derived from the tree (`get_new_url`) | Reshaping the tree changes URLs; `_` URLs can't be reproduced |
| `get_legacy_url()` returned the *parent's* URL for `_` gaps | Wrong canonical URLs |
| Path lookup assumed depth == `admin_level` | `/_/` paths and flexible trees couldn't resolve |
| Model said `short_name` was globally unique; the database said unique per parent | Tests and production disagreed |
| Descendant queries walked the tree in Python, one query per node | Slow for large countries |
| Four nullable legacy foreign keys | Ambiguous mappings, no idempotent rebuild |
| `get_localities()` returned a 5th value (the node) | **Live bug:** spot add, spot patch, add-place-id and shop geocoding crash whenever Google returns a country (they unpack 4 values) |

Production state (Oct 15, 2026): **0 of 12,215 spots** point at a node, and the `/loc/<path>` API routes return 404. The `/spot/geocode` route could create some node rows, but they're all derived from the legacy tables. Nothing is lost by dropping them.

## Migration steps

Each step is its own PR, safe to deploy alone, and can be rolled back.

### Step 1: `Place` replaces `GeographicNode` *(this PR)*
- Add the `Place` model, migration `7c1d2e3f4a5b`, the builder (`app/helpers/places.py`) and `scripts/build_places.py`.
- Drop `geographic_node`, `spot.geographic_node_id`, `dive_shop.geographic_node_id`, the `/loc/<path>` routes, `URLMappingService` and the two old migration scripts.
- `Spot.get_url()` always returns `/Beach/<id>/<slug>`.
- `get_localities()` returns 4 values again, which fixes the geocoding crash.

Production behavior change: only the geocoding fix. Nothing reads `Place` yet.

### Step 2: Build the tree on a copy of production and check parity
1. Copy the production database to staging and run `python scripts/build_places.py` (dry run). Review the counts and problem lists: `no_country`, `no_url`, `duplicate_path`, `duplicate_slug`.
2. Fix the legacy data until the problem lists are empty or understood, then `--apply`.
3. **Parity check script** (to write). Fail if any of these is off:
   - Every URL in today's sitemaps and in the Search Console top pages resolves (`get_place_by_path`) to one place.
   - For each place, the spots in its subtree equal what `/spots/get` returns for its URL.
   - Every verified, non-deleted spot, and every shop with a location, has a `place_id`.
4. Run in production. The builder only adds places and sets `place_id`; legacy tables are untouched, and it's safe to re-run.

### Step 3: Switch reads, one endpoint at a time
Behind flags where practical, comparing old and new output in logs for a few days:
1. `/locality/stats`: filter `Spot.place_id IN place.subtree_ids_query()`. The response stays the same.
2. Sitemaps: list places by `path`. This adds the missing `/_/` pages.
3. `/locality/*` lists and the `area` block in `/spots/get`.
4. A new `/places/<path>` endpoint; frontend location pages read it, at the same URLs.

### Step 4: Switch writes
- Geocoding assigns `place_id` directly, while the legacy foreign keys are still written during the transition.
- The location edit endpoints (`routes/loc.py`) edit places.
- Re-run `build_places.py` nightly until writes are switched, to catch drift.

### Step 5: Flexible geography
- Add "also in" links and a redirects table.
- Create island, marine-park and cross-border region places for the roadmap 1.8 guides. They get new URLs, so nothing redirects.
- Fill gaps by moving places under real parents (`move_to`). Paths don't change.

### Step 6: Retire the legacy tables
After a full season (fall 2027) with no reads: stop writing the legacy foreign keys, then drop `country` / `area_one` / `area_two` / `locality`, `legacy_type` and `legacy_id`.

## Rollout and rollback

- **Step 1:** migration `7c1d2e3f4a5b` runs automatically on deploy (`release: flask db upgrade`). It was tested on local Postgres (upgrade, downgrade, re-upgrade, no model/schema drift, build script end to end). Rollback: `flask db downgrade c41ee6a08991` recreates an empty `geographic_node` schema.
- **Step 2** only adds rows.
- **Step 3** switches are per endpoint, behind flags; legacy tables stay intact.
- After each frontend switch, watch Search Console (404s, "Page with redirect", indexed count) for 2 weeks.

## Timeline

| Step | Target |
|---|---|
| 1 | Oct 2026 (this PR) |
| 2 | Early Nov 2026 |
| 3 | Nov 2026; roadmap Phase 1 (1.2+) builds on Place-backed endpoints |
| 4 | Dec 2026 |
| 5 | Jan 2027, ahead of the roadmap 1.8 guides |
| 6 | Fall 2027 |

## Open questions

1. Spot URLs: keep `/Beach/<id>/<slug>` permanently? Recommended: yes. They rank, and moving 12k URLs carries the same risk as above.
2. Do any shorediving.com-era location aliases need their own places, or are the nginx 301s enough?
