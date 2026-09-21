# Arena-first polo property research

Brief updated 2026-09-21. Active route: `/investors/` (the existing `/investors.html`
redirect is unchanged).

## Acquisition brief

- Minimum **20 parcel acres**, inclusive; no maximum acreage or assumed budget.
- **Flat, contiguous usable polo land is required.** A listing claim, pasture,
  favorable historic score, or large total acreage does not establish flatness.
- **Arena first**, with a separately assessed grass format. Record whether the
  grass plan supports training/reduced play or a full field. Neither a 20-acre
  parcel nor a claimed flat area establishes that both layouts fit.
- **I-77 south of Charlotte toward Columbia**, at most **45 minutes from Uptown
  Charlotte**, inclusive. Uptown retains the previous dashboard's origin. No
  35-minute lower bound. Columbia describes direction, not a second travel hub.
- Expansion is optional. Document usable reserve land or an actual assemblage
  opportunity; don't infer expansion rights from a neighboring empty parcel.

`data/property-search-brief.json` supplies thresholds, scoring weights and active
search-source URLs to the new page and refresh entry point. Search pages cover
Mecklenburg, York and Chester counties at 20+ acres. County scope is only a
collection boundary, not proof of I-77 frontage, flatness or a qualifying route.
North-of-Uptown coordinates, explicitly different corridors and over-limit legacy
estimates stay outside the current screen until better evidence resolves them.
The latitude boundary at Columbia is a coarse directional check, not a route map.

## What changed

The investor route now loads `property-research-core.js` and
`property-research.js`, not the old investor code in `script.js`. Public pages
continue using their original shared bundle. The main map, team votes, source
links and Worker-triggered refresh remain. The old mile-radius circles are removed;
they were not drive-time isochrones. Card mini-maps are replaced by one filtered
regional map and per-property driving links to keep the page lighter.

The active refresh command is:

```sh
python scripts/refresh_property_research.py --summary-path property-refresh-summary.json
python scripts/refresh_property_research.py --validate-only
```

The unchanged `update-properties.yml` workflow name and Worker endpoint now run
this entry point, so no Worker redeployment is required for this change. The old
`scripts/update_properties.py` is retained only as the existing fetch/parser
library. Its old normalization, target selection, scoring, main routine and
50-acre search settings are **not** called by the active refresh. Do not run its
old CLI for this brief. Historical documentation referring to that command
predates this change.

Historical CSV rows and analyst fields are retained, not rewritten as suitable
sites. The seven pre-change listings have no documented flatness/layout/route
qualification under this brief, and have recorded distance or corridor conflicts.
Their May 2026 source dates must not be interpreted as a current listing check.
No new listings or fabricated evidence are seeded by this implementation.

## Evidence fields

Evidence URLs must be HTTP(S); review dates must be actual, non-future `YYYY-MM-DD`
dates. The UI checks the presence and format of this analyst-recorded evidence;
it does **not** fetch a survey and verify its conclusions. A status without a
valid source and date cannot pass a required check.

| Check | Fields | Passing status |
| --- | --- | --- |
| Terrain | `Terrain Status`, `Terrain Evidence`, `Terrain Checked At` | `verified-flat` |
| Corridor | `Corridor Status`, `Corridor Evidence`, `Corridor Checked At` | `verified` |
| Drive | `Verified Drive Minutes`, `Drive Origin`, `Drive Evidence`, `Drive Checked At` | Positive route time <=45, origin `Uptown Charlotte` |
| Arena | `Arena Fit`, `Layout Evidence`, `Layout Checked At` | `verified` |
| Grass | `Grass Fit`, `Layout Evidence`, `Layout Checked At` | `verified-training` or `verified-full-field` |
| Expansion | `Expansion Status`, `Expansion Evidence`, `Expansion Checked At` | Optional `verified` |

Use `unverified` for unknown statuses; `claimed-flat` for a terrain claim;
`unsuitable` for a negative terrain/arena/grass assessment; `outside` for a
negative corridor assessment; `possible` or `unavailable` for expansion.
`Terrain Notes` and `Usable Flat Acres` preserve useful footprint details.

Legacy `Drive Time From Charlotte` / `Est. Drive Min to Charlotte` values remain
explicitly **unverified estimates**. An estimate over 45 minutes is outside the
screen, not conclusive proof of an actual journey time. A valid recorded route
check supersedes it. Range inputs use their upper bound. Unknown time is never
zero or calculated from straight-line miles. Record departure-day/time context
in the linked route evidence and revisit it before arranging a site visit.

The refresh preserves unknown/custom columns and manual exclusions, never fills
these evidence statuses as verified, and revokes pass statuses when recorded
acreage or coordinates change. Evidence links remain for historical review.
Source parsing is not verification of current availability, permitted uses,
flatness, drainage or safe field geometry.

## Eligibility and ordering

- **Meets documented brief:** every required check passes. This is still not an
  engineering, permitting, legal or purchase recommendation.
- **Needs verification:** no recorded hard conflict, but at least one check is
  unknown. These are leads, not confirmed matches.
- **Outside current brief:** one or more conflicts, recorded inactive status or
  manual exclusion. Available in the archive view without deletion.

Order by status first, then documented-fit points. Terrain 40; arena 25; grass
15; corridor plus drive 10; minimum acreage 5; optional expansion 5. Price, votes,
legacy scores and extra acreage cannot override a failed required check. Missing
prices/drives sort last, rather than as free land or zero-minute journeys.

## Refresh integrity and testing

The existing daily schedule and on-demand dispatch are retained. The refresh
collects from the new county/acreage sources, records per-source failures and
provenance, caps listing-page requests, preserves archival data, and writes
atomically only when meaningful listing fields change. Audit-only timestamp
changes do not rewrite the CSV. Severe source failures block writes by default;
`--allow-source-failures` is an explicit operator override. `--dry-run` never
writes the CSV. HTTP success does not imply terrain qualification.

```sh
node --check property-research-core.js
node --check property-research.js
node --test tests/property-research-core.test.cjs
python -m unittest discover -s tests -p 'test_property_research.py'
python scripts/refresh_property_research.py --validate-only
```

`Property Research Checks` runs these checks for relevant pull requests and main
pushes; the scheduled refresh runs the unit tests before collecting listings.
An additional local Chromium smoke test exercised the access gate, filters,
empty/archive view, vote/toggle, refresh messaging, unsafe-link/text handling and
missing-map fallback using synthetic records and mocked network responses. It
was not a live Worker, live listing-source or production-stylesheet test.

## Existing access limitation

The existing session-based access-code gate is retained, with storage errors
handled safely. It is **not authentication**: the code, CSV and page are publicly
hosted. The page now says so. Keep confidential investor information and private
survey documents out of this public repository. Real access control and the
existing vote-service trust model are separate security work, not solved here.
