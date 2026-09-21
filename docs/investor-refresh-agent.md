# Property research refresh setup

Current route: `/investors/`, release `2026-09-21-r2`. The brief is 20+ parcel
acres, flat usable polo land, arena-first plus a separately assessed grass format,
I-77 south toward Columbia, maximum 45 minutes from Uptown Charlotte, and optional
expansion. See `property-research-brief.md` for the evidence fields.

## Data flow

The scheduled/on-demand **Update Property Dataset** workflow runs
`scripts/property_pipeline.py`. The CSV remains the editable research ledger.
`data/property-research.json` combines the ledger, current brief, source-health
report, checksum and workflow run ID in one snapshot.

The page reads the latest raw-GitHub snapshot with labeled fallbacks. After a
completed refresh, it checks current repository contents through the public
GitHub API when raw-file CDN propagation is behind. It reports completion only
when the displayed snapshot's run ID matches the completed job. API failure or
rate limiting preserves an explicitly older snapshot rather than inventing a
successful handoff. No browser GitHub token is used.

**Check for new properties** starts a source check. **Reload results** reloads
saved research. Request accepted, job completed, matching snapshot published and
successful source coverage are different states. Failure reports can be committed
without changing old listing-review dates; failed source jobs still fail visibly.

## Public-source coverage

The pipeline checks configured public York/Chester broker pages with robots
rules, a transparent user agent and bounded requests. Blocked major portals are
paused rather than bypassed. A rendered zero count may omit dynamic inventory;
it is not a market-wide no-results finding. Broader dependable coverage needs
appropriate additional sources or an authorized feed.

Listing checks do not certify availability, flatness, route times, layout,
drainage or permitted use. Job/snapshot timestamps must not replace source dates.

## Existing Cloudflare service

Endpoint: `https://refresh-properties.charlottepolo-refresh.workers.dev`.
Repository source: `workers/refresh-properties.js`. A GitHub commit does not
redeploy that Worker. Existing settings are `GITHUB_REPOSITORY=Ballzatram/cltpolo`,
`GITHUB_WORKFLOW=update-properties.yml`, `GITHUB_REF=main`, and
`ALLOWED_ORIGIN=https://charlottepolo.com`. `GITHUB_TOKEN` stays a server-side
secret with repository Actions permission; never place it in browser files.

A September 21 live Chromium check received HTTP 202 from the real refresh
endpoint and started successful workflow run `35627639476`. A Python diagnostic
was rejected with Cloudflare error 1010; that was not proof of browser failure.

Shared voting remains a separate deployed-service limitation: the real `/votes`
GET returned HTTP 405. The UI hides unavailable shared voting. **Save for review**
is device-local browser storage, not a shared vote or synced account. Shared votes
require the matching Worker deployment and a `PROPERTY_VOTES` KV binding.

## Verification

```sh
node --test tests/property-research*.test.cjs
python -m unittest discover -s tests -p 'test_property*.py'
python scripts/property_pipeline.py --snapshot-only
python scripts/property_pipeline.py --validate-only
python tests/property_browser_smoke.py
```

**Property Research Checks** uses actual HTML/CSS/JavaScript with mocked external
services. It tests mobile/desktop behavior, stale-CDN recovery through the contents
API, exact completed/displayed run IDs, and failure when a job finished but its
snapshot is unavailable. A success-looking message alone must never pass that test.

**Verify Property Release** is now read-only: it verifies deployed page/assets,
corrected handoff code and snapshot structure without launching repeated production
searches on every frontend commit. This is not a claim of end-to-end job completion
or comprehensive source coverage. The earlier live report's permissive text-match
assertion was replaced after inspection exposed an older cached snapshot.

The older `update_properties.py` and `refresh_property_research.py` CLIs are
historical, not active workflow entry points.

The public client-side access-code gate is a convenience, not secure
authentication. Do not publish confidential investor or survey documents here.
