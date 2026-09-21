# Property research refresh setup

Current acquisition and data behavior is documented in
[`property-research-brief.md`](property-research-brief.md). The public research
page is `/investors/`; release `2026-09-21-r2` replaces the old 50-acre dashboard.

## Active data flow

1. The scheduled or on-demand **Update Property Dataset** workflow runs
   `python scripts/property_pipeline.py`.
2. `data/property-search-brief.json` defines the 20-acre minimum, flat usable
   terrain requirement, arena-first plus separate grass format, I-77 south
   corridor, and 45-minute maximum from Uptown Charlotte. Expansion is optional.
3. Public broker sources are checked with robots rules, bounded requests and no
   access-control bypass. Blocked major portals are paused and disclosed.
4. The CSV remains the editable research ledger. An atomic
   `data/property-research.json` snapshot combines that ledger with the current
   brief, source-health report, checksum and workflow run ID.
5. The page reads the latest raw-GitHub snapshot, with explicitly labeled
   deployed/ledger fallbacks. It does not depend on a Pages rebuild for every
   workflow-token data commit.
6. Failure reports can be published without changing old listing-review dates.
   The workflow still fails when the source job fails; failure is not concealed.

The main controls are **Check for new properties** and **Reload results**. A
refresh request, workflow completion, published snapshot and successful source
coverage are distinct states. Job success is not a complete market search.

## Existing Cloudflare refresh service

The page calls `https://refresh-properties.charlottepolo-refresh.workers.dev`.
Repository source is `workers/refresh-properties.js`. A GitHub commit does not
redeploy that Worker; confirm the actual deployed service separately.

The Worker configuration is:

| Setting | Value |
| --- | --- |
| `GITHUB_REPOSITORY` | `Ballzatram/cltpolo` |
| `GITHUB_WORKFLOW` | `update-properties.yml` |
| `GITHUB_REF` | `main` |
| `ALLOWED_ORIGIN` | `https://charlottepolo.com` |
| `GITHUB_TOKEN` | Server-side secret with repository Actions read/write access |

Never place the token in browser files or ask a visitor to paste an owner token.
Verify the service from the actual browser origin. A Python HTTP probe rejected
by Cloudflare with error 1010 is not conclusive evidence that a normal browser
request will fail; the release workflow tests the actual live Chromium flow.
Do not weaken protection or spoof clients merely to make a diagnostic pass.

## Shared voting and local saved research

Shared voting needs the current Worker deployed and a `PROPERTY_VOTES` Workers KV
binding. Repository code alone does not establish deployment. The September 21
inspection observed HTTP 405 from the deployed `/votes` endpoint; the page only
shows shared voting after a valid service response.

**Save for review** uses local browser storage and remains usable without that
service. It is explicitly device-local, not a shared team vote or synced account.

## Verification commands

```sh
node --test tests/property-research*.test.cjs
python -m unittest discover -s tests -p 'test_property*.py'
python scripts/property_pipeline.py --snapshot-only
python scripts/property_pipeline.py --validate-only
python scripts/property_pipeline.py --dry-run
python tests/property_browser_smoke.py
```

`Property Research Checks` tests the actual HTML/CSS/JavaScript on mobile and
desktop with mocked external services. `Verify Property Release` separately
checks published assets/snapshot and performs one real on-demand refresh through
the live browser page. Inspect both; a green unit test is not proof of deployment.

The older `scripts/update_properties.py` and
`scripts/refresh_property_research.py` entry points are historical and are not run
by the active workflow. Do not use their old criteria or search settings.

## Data and access limitations

Source dates describe the last actual page review, not the latest job timestamp.
A rendered empty broker page may omit dynamically loaded inventory; it is not a
market-wide no-results finding. Broader dependable coverage requires appropriate
additional sources or an authorized feed. No listing claim verifies flatness,
routing, field layout, zoning or availability by itself.

The existing client-side access-code gate is a convenience, not authentication.
The repository and research files are publicly hosted; confidential investor
information and private survey documents must not be published there.
