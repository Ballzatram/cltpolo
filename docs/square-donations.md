# Square donation setup

The public `/become-a-member` page links to the dedicated checkout at `https://cltpolo-donations.pages.dev/become-a-member/#donate`. The checkout is hosted separately because Cloudflare Pages can send the `frame-ancestors 'none'` response policy that GitHub Pages cannot.

The checkout uses Square's Web Payments SDK. Card data is entered in Square's hosted field and tokenized in the browser. The browser sends only the resulting one-use payment token, amount, idempotency key, and email address to the dedicated `donations` Cloudflare Worker.

The Worker is deliberately separate from `refresh-properties`. It holds only Square credentials and creates the charge with Square's Payments API.

## Before deployment

1. Confirm that the Charlotte Polo Club Square seller account is activated for production payments.
2. In the Square Developer Console, create or select the application used for the website.
3. Collect the credentials from the same environment:
   - Application ID
   - Location ID
   - Access token
4. Confirm the location accepts USD payments.
5. Confirm the club can accept payments described as donations under its organizational status and Square's current terms. The website intentionally makes no tax-deductibility claim.

Sandbox and production credentials cannot be mixed. The SDK URL, API host, application ID, location ID, and access token must all belong to the same Square environment.

## Configure the production Worker

Create an ignored production secrets file from the tracked placeholder, then replace every placeholder value:

```bash
cp .dev.vars.example .env.production
```

Upload the three encrypted secrets and deploy the Worker together:

```bash
npx wrangler deploy --config wrangler.donations.jsonc --env="" --secrets-file .env.production
```

The Wrangler configuration declares all three credential names as required, so deployment fails closed if any are missing. Delete the local `.env.production` file after deployment if it is no longer needed; git ignores it either way.

The secure checkout expects the Worker at:

```text
https://donations.charlottepolo-refresh.workers.dev
```

That hostname follows the Cloudflare account subdomain already used by the investor Worker. If Cloudflare assigns a different hostname or a custom domain is used, update both of these values in `_checkout/become-a-member/index.html`:

- `data-square-endpoint` on `#donationForm`
- the Worker origin in the page's `connect-src` Content Security Policy directive

Do not add `SQUARE_ACCESS_TOKEN` to HTML, browser JavaScript, Wrangler `vars`, screenshots, logs, or documentation.

## Sandbox verification

The `sandbox` Wrangler environment deploys as `donations-sandbox`, sets `SQUARE_ENVIRONMENT=sandbox`, and accepts browser requests only from the dedicated staging origin `https://cltpolo-donations-sandbox.pages.dev`:

```bash
cp .dev.vars.example .env.sandbox
npx wrangler deploy --config wrangler.donations.jsonc --env sandbox --secrets-file .env.sandbox
```

Use an HTTPS staging or preview page that points `data-square-endpoint` and `connect-src` to the deployed sandbox Worker. Square requires a secure browser context. Use only Square's documented Sandbox card values, then confirm the payment in the Sandbox Square Dashboard.

For local Worker development, copy `.dev.vars.example` to `.dev.vars` and fill it with Sandbox credentials. `.dev.vars` and `.env` variants are ignored by git.

## Deploy the production checkout

The tracked checkout source lives in `_checkout/`, which Jekyll excludes from the GitHub Pages build. Its build script copies only the checkout HTML, response-header policy, redirects, favicon, public navigation script, shared donation client, shared stylesheet, and the one required image. It does not copy investor pages or scripts, property data, Workers, credentials, tests, or repository configuration.

Build into a new empty temporary directory and deploy that explicit artifact:

```bash
checkout_output="$(mktemp -d)"
bash _checkout/build.sh "${checkout_output}"
npx wrangler pages deploy "${checkout_output}" --project-name cltpolo-donations --branch main
```

The stable production URL is:

```text
https://cltpolo-donations.pages.dev/become-a-member/
```

Deploy the Worker before deploying the checkout, and deploy the checkout before merging a main-site link change. This keeps donors away from an unavailable form.

## Runtime controls

`wrangler.donations.jsonc` configures:

- production origin allowlist: `https://cltpolo-donations.pages.dev`
- currency: USD (fixed in Worker code)
- minimum donation: $5
- maximum donation: $5,000
- per-client payment attempts: 5 per minute in production
- total payment attempts: 30 per minute per Cloudflare location in production
- request bodies: streamed and rejected above 10,000 bytes before JSON parsing
- Workers Logs: enabled with structured unexpected-error events that omit messages, bodies, donor data, and credentials
- Square API version: `2026-07-15` (pinned in `workers/donations.js`)

The Worker validates the amount again on the server, requires a buyer email, uses a client-generated UUID idempotency key, confirms Square returned a `COMPLETED` payment for the expected amount/location/currency, and returns only a payment ID and receipt URL. It never returns the access token or Square's raw error response. The successful checkout shows Square's receipt URL; the Payments API does not guarantee that entering `buyer_email_address` sends an email receipt.

CORS is not authentication. The Worker also fails closed unless both Cloudflare rate-limiter bindings are present, but Cloudflare's binding is eventually consistent and applies within each Cloudflare location. Before production, configure Square Risk Manager and consider Turnstile or a Cloudflare WAF rule if abuse patterns appear. Add a verified Square webhook later if the club needs automated fulfillment or accounting workflows; a browser success message alone should not drive those workflows.

## Hosting security headers

The checkout's `_headers` file configures Cloudflare Pages to send an HTTP Content Security Policy that includes:

```text
Content-Security-Policy: frame-ancestors 'none'
```

This prevents another site from framing the checkout and presenting it as a click target. The same response also sends `X-Frame-Options: DENY`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, a restrictive permissions policy, and `X-Robots-Tag: noindex, nofollow, noarchive`.

The production Square and Worker origins are defined only in `_checkout/_headers`. The main GitHub Pages membership page has a self-only meta policy and contains no Square form, endpoint, or Square SDK loader.

## Checks

Run the repository checks:

```bash
node --check donation.js
node --check workers/donations.js
node --test tests/*.test.mjs
```

Then verify the form on small mobile, large mobile, tablet, laptop, and wide desktop widths. Confirm the stable Pages response includes `frame-ancestors 'none'` and `X-Frame-Options: DENY`. Test loading, validation, decline, uncertain-network, and completed-payment states before switching the Worker to production credentials. A production deployment check must stop after the real card field reaches its ready state; do not create a real charge solely as a smoke test.

## Square references

- Web Payments card flow: https://developer.squareup.com/docs/web-payments/take-card-payment
- Web Payments SDK setup: https://developer.squareup.com/docs/web-payments/quickstart/add-sdk-to-web-client
- Payments API: https://developer.squareup.com/reference/square/payments-api/create-payment
- Content Security Policy: https://developer.squareup.com/docs/web-payments/content-security-policy
- Production deployment: https://developer.squareup.com/docs/web-payments/quickstart/deploy-app
