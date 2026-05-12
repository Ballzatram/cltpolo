# Investor CSV refresh agent setup

The land dashboard is a static page, so it cannot safely store an owner GitHub token in browser JavaScript. To make **Refresh CSV Now** work for investors without GitHub accounts, put the GitHub credential in a tiny server-side endpoint and let the dashboard call that endpoint.

This repository includes a Cloudflare Worker example at `workers/refresh-properties.js`.

## One-time setup

1. Create a fine-grained GitHub personal access token for the repository.
   - Repository access: `Ballzatram/cltpolo` only.
   - Permissions: **Actions: Read and write**.
   - Set an expiration date and rotate it periodically.
2. Deploy `workers/refresh-properties.js` as a Cloudflare Worker.
3. Add these Worker secrets / variables:
   - `GITHUB_TOKEN`: the fine-grained token from step 1. Store this as a secret, not a plain variable.
   - `GITHUB_REPOSITORY`: `Ballzatram/cltpolo`.
   - `GITHUB_WORKFLOW`: `update-properties.yml`.
   - `GITHUB_REF`: the branch that runs the workflow, usually `main`.
   - `ALLOWED_ORIGIN`: `https://charlottepolo.com`.
4. Route the Worker to `https://charlottepolo.com/api/refresh-properties` or update the `data-refresh-endpoint` attribute on the dashboard button to the Worker URL.
5. Test from the investor dashboard by clicking **Refresh CSV Now**. The button starts the GitHub Actions workflow immediately; the CSV appears after the workflow commits and the site redeploys.

## Security notes

- Do not put the GitHub token in `investors.html`, `script.js`, or any other browser-delivered file.
- Do not ask investors to paste your GitHub credentials.
- Consider adding Cloudflare rate limiting, Turnstile, or an authenticated access layer before sharing the dashboard widely.
