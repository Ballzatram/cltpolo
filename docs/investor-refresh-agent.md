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

The GitHub workflow runs `scripts/update_properties.py`. The script reads the existing CSV, refreshes tracked listings and 50+ acre search pages, preserves existing rows, appends newly discovered eligible listings, stamps research dates, and commits `data/charlotte_polo_properties.csv` when the dataset changes.

## Security notes

- Do not put the GitHub token in `investors.html`, `script.js`, or any other browser-delivered file.
- Do not ask investors to paste your GitHub credentials.
- Keep the Worker `ALLOWED_ORIGIN` set to `https://charlottepolo.com` unless you intentionally add another production origin.
- Consider adding Cloudflare rate limiting, Turnstile, or an authenticated access layer before sharing the dashboard widely.
