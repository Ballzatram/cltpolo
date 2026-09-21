# Property collection repair — September 21, 2026

## Root cause

The active collector previously used only two Advance Land & Timber county indexes.
Both returned a rendered zero-listing count. The old health classifier treated a
readable empty index as a successful, limited check even when it parsed no actual
property pages. Repeated dispatches could therefore produce new report timestamps
without any new or rechecked property records.

A public-source diagnostic from the actual GitHub runner found real inventory on
Mossy Oak Properties' York, Chester and Mecklenburg county pages. Changing URLs
alone was insufficient: the parser missed the optional `External ID/MLS` label,
which could corrupt the primary ID and reject an otherwise valid property. It also
hardcoded the source publisher and used the first title occurrence rather than
the actual H1 boundary.

## Repair

- Use a fixed registry for the two supported publishers. Five configured county
  indexes now cover Mossy Oak Properties (York, Chester, Mecklenburg) and Advance
  Land & Timber (York, Chester). These are not five independent brokerages.
- Parse individual primary listing facts, including optional MLS references.
  Require page ID to match URL ID. Ignore neighboring listing cards and metadata.
  Never use a price-per-acre value as the total price.
- Deduplicate by publisher and numeric listing ID, tolerating title-slug changes.
  Preserve manually excluded records and analyst evidence. Recheck supported
  tracked pages even if they disappear from an index.
- Retain newly discovered, in-scope research records only when not advertised as
  sold, under contract or pending. Existing records can change to those statuses.
- Keep each record's source-check date separate from the report publication date.
  An unsuccessful detail request does not advance that record's review date.
- Count actual listing pages parsed, new records, changed records, excluded
  out-of-scope/unavailable listings, and field names changed. Zero successfully
  parsed individual listings is an error, not a successful listing refresh.
  Successfully reading unchanged records can correctly produce zero new/changed.
- Bound requests and rotate the listing budget between runs. Flag reported
  inventory that exceeds collected links; do not claim full pagination coverage.
- Store short factual summaries and attributed constraint signals rather than
  copying whole marketing descriptions. Broker terrain/travel statements never
  become surveyed flatness, verified drive minutes or layout approval.

The existing daily/on-demand workflow and atomic research snapshot are retained.
The repair needs no new API token and changes no Cloudflare deployment or secrets.
The navy/gold theme, CSS, page layout, 20-acre threshold, 45-minute threshold and
arena-first priorities are unchanged. The HTML change only versions the updated
core-rule script so cached clients receive its source-constraint check.

## Tests and live validation

`tests/test_property_sources.py` covers optional MLS labels, primary facts, source
identity, unsafe URLs, deduplication, substantive changes, unavailable listings,
zero-record failures, preserved evidence, bounded rotation and source constraints.
The fixture is a simplified synthetic reproduction of the observed DOM, not a
copy of a broker's marketing page.

`Property Discovery Live Check` fetches public sources through the same allowlisted,
robots-aware, bounded client used in production. It must parse real individual
properties; it replays captured responses in memory to prove unchanged listings
do not create duplicates or phantom changes. It never writes the production ledger.
Its artifact records factual preview rows and source-health counts. This is separate
from deterministic unit/UI tests, whose network services are mocked.

Commands:

```sh
python -m unittest discover -s tests -p 'test_property*.py'
node --test tests/property-research*.test.cjs
python scripts/property_pipeline.py --dry-run --summary-path property-preview.json
```

## Limits

This is configured public-broker coverage, not a complete MLS feed. Portal records
whose sources remain paused retain their original review dates; they are not
refreshed simply because another publisher was checked. New research records do
not imply new listings on the market or qualified flat, within-45-minute polo land.
Full routing, parcel topography, drainage, permitted use and arena/grass layout
remain separate verification work. No requirement is relaxed to fill the screen.
