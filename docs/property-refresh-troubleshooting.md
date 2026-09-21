# Property research operational checks

Use `/investors/` and check the footer release identifier (`2026-09-21-r2`).
A branch or PR change is not a live deployment. Verify the actual page after merging.

The current data entry point is `scripts/property_pipeline.py`. Earlier setup
instructions describing `scripts/update_properties.py` or
`scripts/refresh_property_research.py` are historical.

The latest `data/property-research.json` must match the ledger checksum and current
brief, and its source-health report must be considered separately from job success.
A failed research step is allowed to publish a validated failure report before the
workflow is marked failed. It must never replace old listing review dates with the
job date. Reload results should show the latest snapshot without a Pages rebuild.

A 405 response from the deployed shared-vote endpoint means the shared service is
unavailable. Local saved properties are explicitly device-only and are not votes.
The page's client-side code gate is not secure authentication.

If the source-health report says limited coverage, do not describe the result as a
complete search. Public broker inventory can differ from a portal's market coverage.
Do not bypass blocked providers or silently introduce paid data services.
