# Property research — active implementation (2026-09-21-r2)

The production route is `/investors/`. The brief remains: at least 20 parcel acres;
flat contiguous usable polo land; arena first, with a separate grass format;
I-77 south toward Columbia; at most 45 minutes from Uptown Charlotte; expansion
optional. Training grass is not represented as a full-size field.

## Audit findings

The previous PR was still unmerged when the user reported outdated copy. A real
GitHub runner request confirmed the public page still said 50+ acres and exposed
CSV refresh mechanics. Scheduled run `35517092467` (2026-09-20) tried 28 discovery
pages: all failed (403, and Realtor.com 429), no rows changed, and no CSV was
written. The failure report was only an Actions artifact, not visible in the UI.
The deployed `/votes` endpoint returned HTTP 405 even though repository Worker
code defined a GET handler. Repo source and deployed Worker are not the same thing.

References: repository runs `35517092467` and `35622652957`. These are dated
observations, not claims that provider access can never change.

## Active data path

1. `data/property-search-brief.json` defines the brief, public broker discovery
   pages, paused portals, and human-readable wider-market search links.
2. `scripts/property_pipeline.py` reads the existing CSV ledger, checks permitted
   public broker sources, and preserves historical and analyst-entered records.
3. It writes **one atomic** `data/property-research.json` containing the brief,
   property rows, ledger checksum, source-health report, code SHA and run ID.
4. The workflow validates and commits the snapshot even when the source run fails.
   A final step still marks a failed source run as failed; `continue-on-error` is
   used only to make failure reporting publishable, not to hide failure.
5. The browser reads the latest raw-GitHub snapshot, then explicitly labeled
   deployed/ledger fallbacks. It does not depend on a Pages rebuild for every
   data update. GitHub workflow-token commits do not trigger Pages branch builds:
   https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
6. A refresh request stays on-page. Public GitHub workflow status is checked at
   bounded intervals, and the page waits for a snapshot with the matching run ID.
   Dispatch accepted, job completed, snapshot published and sources checked are
   distinct states. A failed/rate-limited status request never invents completion.

## Honest coverage

Major blocked portals are paused, not scraped through proxies or CAPTCHA bypass.
The initial replacement provider is Advance Land & Timber's public York and
Chester county pages, with robots-policy checks and a transparent user agent.
Its main site and robots policy were reachable from the actual runner during the
inspection. This is **limited broker coverage**, not the whole market and not
coverage of every Mecklenburg parcel. Human browsing links remain available.

A rendered zero-listing count can omit dynamically loaded inventory. The job
reports `empty-rendered`, explicitly not a comprehensive no-results search.
HTTP 200 with unrecognized markup is `unparsed`, not success. HTTP/network/robots
failures preserve saved records. Requests are host-allowlisted, size/time bounded,
limited per run, and cease on an access block for that host.

`limited` and `partial` source reports are never labeled complete market success.
An authorized broker/MLS/search feed would be needed for broader reliable
coverage; no new paid service or API key is silently assumed or configured.

## Dates and suitability

`Listing Checked At` means the public source page was actually retrieved and
parsed. It is separate from snapshot/job timestamps and does not certify current
availability. Failed checks never refresh old source-review dates. Reviews older
than the configurable 30-day display threshold get stale badges. Neither an HTTP
200 nor a listing saying "flat" verifies terrain, routes, layout or permitted use.

The rule engine still requires dated HTTP(S) evidence for verified terrain,
corridor, route and layout statuses. It validates presence/format, not the
contents of a survey. Legacy estimates above 45 minutes stay outside the screen
until a documented route resolves them. A county name alone is not I-77 access.
Manual exclusions and arbitrary analyst columns survive source refreshes.
Changed acreage/coordinates revoke site pass statuses but retain old evidence
links for historical review. A failed requirement cannot be outweighed by price,
acreage, expansion or team preference.

## Frontend behavior

Main actions are "Check for new properties" and "Reload results". CSV remains
only a technical export. Empty/filter/archive states are explicit. Local saved
properties work without shared voting; the page never implies a local save was
synced to the team. Shared voting appears only after a valid service response.
The existing client-side access-code gate is retained and disclosed as **not
secure authentication**. Do not publish confidential documents in this repo.

## Commands and tests

```sh
python scripts/property_pipeline.py --dry-run
python scripts/property_pipeline.py --snapshot-only
python scripts/property_pipeline.py --validate-only
node --test tests/property-research*.test.cjs
python -m unittest discover -s tests -p 'test_property*.py'
python tests/property_browser_smoke.py
```

The old `scripts/update_properties.py` and `scripts/refresh_property_research.py`
are retained for historical parser/tests only. Their CLIs are **not the active
refresh path**. Older setup documents describing them are superseded here.
The Worker endpoint/workflow identity is unchanged; the new frontend does not
require a new Worker `/status` endpoint. Fixing/deploying the older shared-vote
Worker remains a separate infrastructure task, not falsely claimed by this page.

The browser suite uses real checked-in HTML/CSS/JS and mocked external services.
It covers mobile/desktop overflow, gate, filters, archive/empty views, script
injection escaping, local saved properties, unavailable maps/votes, dispatch
failure and in-page completion. It does not verify live surveys or broker data.
