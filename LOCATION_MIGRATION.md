# Location hierarchy migration: design doc

Status: Step 1 done; **builder fixes (step 2a) in review**, Oct 2026
Owner: Mayank

## Summary

Replace the four fixed location tables (`Country` → `AreaOne` → `AreaTwo` → `Locality`) with a single tree of **`Place`**s that can be any depth, and **retire the `_` location URLs**: every URL with a `_` (or a broken `None`) segment 301s to a clean URL built from the place's real ancestors. All other location URLs stay exactly the same, and spot URLs remain `/Beach/<id>/<slug>`.

`Place` is new and replaces `GeographicNode`, an earlier attempt from July 2025 that was never switched on and had structural problems (see "Why not GeographicNode").

## Why change the location model

The fixed hierarchy doesn't match real geography, and that has costs we can measure:

1. **Gaps drop out of lists.** Places with no state or county get a `_` in the URL (`/loc/pt/beja/_/vila-nova-de-milfontes`). The location list endpoints (`/locality/*`) inner-join the full chain, so these pages are missing from the sitemaps and directories. 42 of them earned 522 search clicks anyway.
2. **Every query special-cases the levels**: four tables plus `_` wildcards, in `/spots/get`, `/locality/*`, the sitemaps and `/locality/stats`.
3. **Geographies that matter for SEO can't be represented**: islands, atolls, marine parks, and regions that cross borders (Florida Keys, Red Sea). The roadmap's "best places to snorkel in X" guides need them.

## URL policy

*Revised Oct 16, 2026: the original policy kept `_` URLs forever; the decision now is to retire them.*

- **Unchanged:** every location URL without a `_` or `None` segment keeps its exact path.
- **Retired with a 301:** about 1,190 URLs with a `_` (1,123 towns, 65 counties) and 248 with `None` (those already 404). Each gets a clean path from the place's real ancestors: `/loc/pt/beja/_/vila-nova-de-milfontes` → `/loc/pt/beja/vila-nova-de-milfontes`, `/loc/pf/_/tuamotus-islands/rangiroa` → `/loc/pf/tuamotus-islands/rangiroa`.
- **Redirects are permanent data** (`place_redirect`): old path → place. The page resolver 301s any path found there.
- **Trade-off, accepted:** redirected pages usually dip for a few weeks while Google re-crawls (518 of the `_` towns have live spots, 919 spots in total). Done in the off-season so it settles before the March ramp-up.
- Location pages earn 59% of search clicks, so the parity check (step 2c) must pass before the frontend switch.

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

- **`path` is stored, never derived from the tree.** The tree can be reshaped (moving a town under a new island, filling a gap) without touching any URL; a URL changes only by an explicit rename that leaves a `place_redirect` behind.
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

### Step 1: `Place` replaces `GeographicNode` *(done, #57)*
- Add the `Place` model, migration `7c1d2e3f4a5b`, the builder (`app/helpers/places.py`) and `scripts/build_places.py`.
- Drop `geographic_node`, `spot.geographic_node_id`, `dive_shop.geographic_node_id`, the `/loc/<path>` routes, `URLMappingService` and the two old migration scripts.
- `Spot.get_url()` always returns `/Beach/<id>/<slug>`.
- `get_localities()` returns 4 values again, which fixes the geocoding crash.

Production behavior change: only the geocoding fix. Nothing reads `Place` yet.

### Step 2a: Builder fixes *(this PR)*
The first production dry run reported 191 rows it couldn't place. The builder now:
- **Falls back to a computed URL** (same `_` shape as the legacy code) when the stored one is empty or broken: counties with no region had no URL, and 248 towns stored `/loc/xx/None/_/town`.
- **Treats unusable levels as missing.** A level with no Latin-script slug (`الوكرة`, `沖縄県`, a short_name of `-`) gets no place; its children hang off the nearest usable ancestor and its spots go there too (reported as `unusable`).
- **Merges the same place stored twice** under one parent (same slug or same URL, e.g. Kaafu Atoll as a region and as a county): the duplicate maps onto the first place and its URL becomes a `place_redirect` (reported as `merged`).
- New table `place_redirect` (migration `5a6b7c8d9e0f`).

### Step 2b: Clean paths
A script gives every place whose path has `_` or `None` a clean path from its ancestors' slugs (children included) and records the old path as a `place_redirect` (`reason = "clean_path"`). Dry run first, with the full before → after list.

### Step 2c: Build in production and check parity
1. `python scripts/build_places.py` (dry run, `--verbose` for full lists), review, then `--apply`; then the clean-paths script.
2. **Parity check script:** every URL in today's sitemaps and Search Console top pages either resolves to a place at the same path, or (for `_`/`None` URLs) to a redirect whose target resolves; for each place, the spots in its subtree match what `/spots/get` returns today; every live spot and located shop has a `place_id`.

### Step 3: Switch reads, one endpoint at a time
Behind flags where practical, comparing old and new output in logs for a few days:
1. `/locality/stats`: filter `Spot.place_id IN place.subtree_ids_query()`. The response stays the same.
2. Sitemaps: list places by `path` (clean paths only).
3. `/locality/*` lists and the `area` block in `/spots/get`.
4. A `/places/resolve?path=` endpoint returning the place, a redirect target, or 404, plus page data. The frontend replaces its fixed-depth `/loc/[country]/[area_one]/[area_two]/[locality]` routes with one catch-all route that serves the page or 301s. Clean URLs need this: `/loc/pt/beja/vila-nova-de-milfontes` has the same depth as a county URL, so only a path lookup can tell them apart.

### Step 4: Switch writes
- Geocoding assigns `place_id` directly, while the legacy foreign keys are still written during the transition.
- The location edit endpoints (`routes/loc.py`) edit places.
- Re-run `build_places.py` nightly until writes are switched, to catch drift.

### Step 5: Flexible geography
- Add "also in" links.
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
| 1 | Done (Oct 15, 2026) |
| 2a–2c | Late Oct 2026 |
| 3 (incl. the 301 switch) | Early Nov 2026, off-season; roadmap Phase 1 (1.2+) builds on Place-backed endpoints |
| 4 | Dec 2026 |
| 5 | Jan 2027, ahead of the roadmap 1.8 guides |
| 6 | Fall 2027 |

## Open questions

1. Spot URLs: keep `/Beach/<id>/<slug>` permanently? Recommended: yes. They rank, and moving 12k URLs is a far bigger redirect than the ~1,200 location URLs.
2. Do any shorediving.com-era location aliases need their own places, or are the nginx 301s enough?
