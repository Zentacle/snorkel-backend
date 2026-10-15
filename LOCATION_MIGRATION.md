# Location hierarchy migration: design doc

Status: **Step 1 in progress**, Oct 2026
Owner: Mayank

## Summary

Move location data from four fixed tables (`Country` → `AreaOne` → `AreaTwo` → `Locality`) to the flexible `GeographicNode` tree that was added in July 2025 but never switched on. **Keep every public URL exactly the same.** Spot URLs stay `/Beach/<id>/<slug>`, and location URLs keep their current form, `_` segments included.

## Why

The fixed hierarchy doesn't fit real geography, and that has costs we can measure:

1. **Gaps drop out of lists.** Places with no state or county get a `_` in the URL (`/loc/pt/beja/_/vila-nova-de-milfontes`). The location list endpoints (`/locality/*`) inner-join the full chain, so these pages are missing from the sitemaps and directories. 42 of them earned 522 search clicks anyway.
2. **Every query special-cases the levels.** Four tables, plus `_` wildcards, in `/spots/get`, `/locality/*`, the sitemaps and the new `/locality/stats`.
3. **Geographies that matter for SEO can't be represented**: islands, atolls, marine parks, and regions that cross state lines (Florida Keys, Red Sea, Caribbean). The roadmap's "best places to snorkel in X" guides (1.8) need them.

## Why URLs must not change

- Location pages earn **59% of search clicks** (Search Console, Jun 2025 – Oct 2026), across 4,868 URLs.
- Google doesn't penalize a `_` in a path. `/_/` pages rank and earn clicks today.
- Changing thousands of URLs, even with 301s, usually costs rankings for weeks or months. Doing that before the March–August season would risk the peak for no ranking gain.

**URL policy:** a URL that exists today keeps working, unchanged, as the canonical URL. New nodes (islands, regions) get new URLs, which only adds pages. Renaming an existing URL needs a 301 and a written reason.

## Current state (verified Oct 15, 2026)

| Item | State |
|---|---|
| `GeographicNode` model and migrations (`b4048382b892`, `5274015c42ef`) | In code; tables exist after `alembic upgrade` |
| Migration scripts (`migrate_geographic_hierarchy_fast.py`, `migrate_spots_to_geographic_nodes.py`) | In code; **not run in production** |
| `Spot.geographic_node_id` | **0 of 12,215** spots set |
| `/loc/<path>` API routes (`routes/geography.py`), including a basic `/stats` | Registered; return 404 in production (no nodes) |
| Frontend | Uses only the legacy endpoints (`/spots/get`, `/locality/*`, `/shop/loc`) |

**Problems found in the existing code:**

1. **Spot URLs would silently change.** `Spot.get_url()` returned `/loc/<node path>/<slug>-<id>` as soon as a spot had a `geographic_node_id`. Running `migrate_spots_to_geographic_nodes.py` would have changed dive site URLs in search results, typeahead, review emails, Slack notifications and every API response using `get_simple_dict()`. *(Fixed in step 1.)*
2. **`GeographicNode.get_url()` built new-style paths** from the tree, which differ from today's URLs wherever a level is missing. *(Fixed in step 1: URLs are stored.)*
3. **`get_legacy_url()` couldn't produce `_` URLs.** For a locality with no area_two it returned the parent area's URL. *(Fixed in step 1.)*
4. **`URLMappingService.find_node_by_path()` assumed depth = admin_level**, so `/_/` paths and flexible trees can't resolve. *(Fixed in step 1: path lookup first.)*
5. **The model and database disagree on uniqueness.** The model said `short_name` is globally unique, but the database has `UNIQUE (parent_id, short_name)`, which is the correct rule. Tests built from the model would reject two towns with the same name. *(Fixed in step 1.)*

## Target model

`GeographicNode` stays the single location table:

- **`path`** (new, unique): the public URL path, stored rather than derived, e.g. `/loc/pt/beja/_/vila-nova-de-milfontes`. This is the source of truth for links, canonicals and sitemaps.
- `parent_id`: one parent per node. A tree is enough for now.
- `admin_level`: kept as a loose hint (0 = country … 3 = city). Code shouldn't depend on depth == level.
- Later (step 5): **`kind`** (`country`, `region`, `island`, `marine_park`, `city`, …) and optional **"also in" links** for regions that overlap the tree (e.g. Florida Keys within Florida, Red Sea across Egypt, Sudan and Saudi Arabia).
- `Spot.geographic_node_id` / `DiveShop.geographic_node_id`: the *most specific* node; ancestors are implied.
- The legacy tables become read-only after cutover and are dropped at the end.

## Migration steps

Each step is its own PR, safe to deploy alone, and can be rolled back.

### Step 1: Make URLs data and pin spot URLs *(this PR)*
- `Spot.get_url()` always returns `/Beach/<id>/<slug>`. The node-based form moves to `get_geographic_url()`, which isn't linked anywhere public.
- New column `GeographicNode.path` (unique, nullable for now). `get_url()` returns it when set.
- `get_legacy_url()` returns exactly the URL the legacy API serves today (`get_dict()["url"]`), including `_`.
- `find_node_by_path()` looks up by stored `path` first.
- Model uniqueness aligned with the database: `(parent_id, short_name)`.
- `scripts/backfill_geographic_node_paths.py` fills `path` from the legacy objects and reports conflicts. Not run yet.

No behavior change in production: no nodes exist yet, and spot URLs were already `/Beach/...` because no spot has a node.

### Step 2: Build the tree on a copy of production and check parity
1. Copy the production database to staging.
2. Run `migrate_geographic_hierarchy_fast.py`, `migrate_spots_to_geographic_nodes.py`, then `backfill_geographic_node_paths.py`.
3. **Parity check script** (to write). Fail if any of these is off:
   - Every URL in today's sitemaps and in the Search Console top pages resolves to exactly one node, with the same `path`.
   - For each node, the set of spots under it (node plus descendants) equals the set `/spots/get` returns for the legacy URL.
   - Every verified, non-deleted spot has a `geographic_node_id`, and so does every shop with a location.
   - No duplicate `path` values.
4. Fix the data until parity holds, then run the same scripts in production. They only add rows; legacy tables are untouched.

### Step 3: Switch reads, one endpoint at a time
Each behind a flag where practical, comparing old and new output in logs for a few days:
1. `/locality/stats` (from #55): filter by descendant node ids instead of the legacy foreign keys. The response stays the same.
2. Sitemaps: list nodes by `path`. This adds the missing `/_/` pages.
3. `/locality/*` list endpoints and the `area` block in `/spots/get`.
4. Frontend location pages, still at the same URLs, read from `/loc/<path>`.

### Step 4: Switch writes
- New spots and shops get a node from reverse geocoding (`helpers/get_localities.py`); the legacy foreign keys are still written during the transition.
- The location edit endpoints (`routes/loc.py` `*/patch`) edit nodes.

### Step 5: Flexible geography (this is the payoff)
- Add `kind` and "also in" links.
- Create island, marine-park and cross-border region nodes for the roadmap 1.8 guides. They get new URLs, so nothing redirects.
- Optionally fix gaps by inserting a real parent (e.g. a region for `_`) **while keeping the old `path`**. Only change a path when the SEO case is clear, and always 301.

### Step 6: Retire the legacy tables
After a full season (fall 2027) with no reads: stop writing the legacy foreign keys, then drop `country` / `area_one` / `area_two` / `locality` and the `legacy_*` columns.

## Rollout and rollback

- Steps 1–2 only add data; rollback means ignoring the new columns and rows.
- Step 3 switches are per endpoint, behind flags, and the legacy tables stay intact, so rolling back means turning a flag off.
- After each frontend switch, watch Search Console (404s, "Page with redirect", indexed count) for 2 weeks.

## Timeline

| Step | Target |
|---|---|
| 1 | Oct 2026 (this PR) |
| 2 | Early Nov 2026 |
| 3 | Nov 2026; roadmap Phase 1 (1.2+) builds on the node-backed endpoints |
| 4 | Dec 2026 |
| 5 | Jan 2027, ahead of the roadmap 1.8 guides |
| 6 | Fall 2027 |

## Open questions

1. Does the production database already have the `geographic_node` table (`alembic current`)? The routes return 404, which fits both "no table" and "empty table".
2. Spot URLs: keep `/Beach/<id>/<slug>` permanently? Recommended: yes. They rank, and moving 12k URLs has the same risk as above.
3. Do any shorediving.com-era location aliases need their own nodes, or are the nginx 301s enough?
