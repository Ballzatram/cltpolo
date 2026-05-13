# Investor CSV refresh agent setup

The land dashboard is a static page, so it cannot safely store an owner GitHub token in browser JavaScript. The dashboard calls a Cloudflare Worker instead. That Worker keeps the GitHub credential server-side, dispatches the property update workflow, and exposes a small shared voting API.

This repository includes the Worker at `workers/refresh-properties.js`.

## One-time refresh setup

1. Create a fine-grained GitHub personal access token for the repository.
   - Repository access: `Ballzatram/cltpolo` only.
   - Permissions: **Actions: Read and write**.
   - Set an expiration date and rotate it periodically.
2. Deploy `workers/refresh-properties.js` as the `refresh-properties` Cloudflare Worker.
3. Add these Worker secrets / variables:
   - `GITHUB_TOKEN`: the fine-grained token from step 1. Store this as a secret, not a plain variable.
   - `GITHUB_REPOSITORY`: `Ballzatram/cltpolo`.
   - `GITHUB_WORKFLOW`: `update-properties.yml`.
   - `GITHUB_REF`: `main`.
   - `ALLOWED_ORIGIN`: `https://charlottepolo.com`.
4. Confirm the investor dashboard button has `data-refresh-endpoint="https://refresh-properties.charlottepolo-refresh.workers.dev"`.
5. Test from the investor dashboard by clicking **Run CSV Refresh Agent**. The browser sends a `POST` to the Worker; the browser never asks for, stores, or submits a GitHub token.

## One-time shared voting setup

The thumbs-up / thumbs-down counts persist for all users through Cloudflare Workers KV.

1. Create a Workers KV namespace for property votes, for example `PROPERTY_VOTES`.
2. Bind that namespace to the `refresh-properties` Worker with the binding name `PROPERTY_VOTES`.
3. Redeploy the Worker.
4. Confirm the investor dashboard button has `data-vote-endpoint="https://refresh-properties.charlottepolo-refresh.workers.dev/votes"`.
5. Test from the investor dashboard by clicking a card vote. The browser stores only that visitor's current selection locally so the same visitor can toggle their vote; shared totals come from KV.

## Data refresh behavior

The button starts the GitHub Actions workflow; it does **not** mean new property data was found or committed. The honest success path is:

1. `investors.html` calls `script.js` when **Run CSV Refresh Agent** is clicked.
2. `script.js` sends a `POST` to the Cloudflare Worker refresh endpoint.
3. `workers/refresh-properties.js` dispatches `.github/workflows/update-properties.yml` through GitHub's workflow dispatch API.
4. The workflow runs `python scripts/update_properties.py --summary-path property-refresh-summary.json`.
5. The script attempts public 50+ acre search pages and tracked listing URLs, prints a source/listing/row summary, and writes `data/charlotte_polo_properties.csv` only when listing rows were added or meaningfully updated. Audit-only timestamp changes are skipped unless the script is intentionally run with `--allow-audit-only`.

## Troubleshooting

### How to tell whether the Worker dispatched correctly

- In the browser, a successful button click means the Worker returned HTTP `202` after GitHub accepted `workflow_dispatch`.
- That response only proves the workflow was queued. It does not prove the workflow completed, found listings, or committed CSV changes.
- If the button reports an error, check the Worker logs and verify `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_WORKFLOW`, `GITHUB_REF`, and `ALLOWED_ORIGIN`.

### Where to check GitHub Actions

- Open `https://github.com/Ballzatram/cltpolo/actions/workflows/update-properties.yml`.
- Open the newest **Update Property Dataset** run.
- Review the **Run property update agent** step for the printed refresh summary:
  - sources attempted
  - sources succeeded
  - sources failed
  - blocked/unavailable sources
  - listing URLs discovered
  - candidates processed
  - rows added
  - rows updated
  - whether the run was audit-only
- Download the `property-refresh-summary` artifact when present for machine-readable details.

### How to tell whether the CSV actually changed

- In the workflow log, the commit step prints either `No listing-data changes to commit` or a commit hash.
- In GitHub, inspect `data/charlotte_polo_properties.csv` history. A real dataset refresh should add a new listing row or change listing fields such as source URL, acreage, price, verification status, coordinates, or listing notes.
- The dashboard's **Reload Committed Data** button only reloads the CSV currently deployed/served by the site. Use it after the workflow finishes and a deployment has picked up any commit.

### What 403 source failures mean

- `HTTP Error 403: Forbidden`, `429`, CAPTCHA, or similar blocked/unavailable responses mean the public source refused automated fetching from the GitHub Actions runner or network path.
- The agent does not bypass paywalls, logins, CAPTCHA, or anti-bot protections. It records the failure and moves to alternate public sources such as Land.com, LandWatch, Realtor.com, Zillow, LoopNet, and Crexi search pages when publicly reachable.
- If most search sources fail and no new listing rows are added, the script exits non-zero by default so the Action does not silently commit an audit-only refresh that looks like fresh listing data.
- Existing valid rows are preserved even when sources fail; they should be manually verified before investor decisions.

## Local validation commands

Run these before changing the workflow or CSV behavior:

```bash
python scripts/update_properties.py --validate-only
python scripts/update_properties.py --dry-run --allow-source-failures
```

Use `--allow-source-failures` for local dry runs from networks where public listing sites block automated requests; omit it in CI when you want the reliability gate to fail on source-wide outages.

## Security notes

- Do not put the GitHub token in `investors.html`, `script.js`, or any other browser-delivered file.
- Do not ask investors to paste your GitHub credentials.
- Keep the Worker `ALLOWED_ORIGIN` set to `https://charlottepolo.com` unless you intentionally add another production origin.
- Consider adding Cloudflare rate limiting, Turnstile, or an authenticated access layer before sharing the dashboard widely.
