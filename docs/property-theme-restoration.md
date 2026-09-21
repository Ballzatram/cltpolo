# Original investor theme restored — 2026-09-21-r3

The owner requested reverting the unrequested light/green visual redesign. The
investor route again loads the unchanged original `style.css`: navy/gold, Georgia
serif typography, full club navigation, Investor Portal gate, Land Acquisition
Dashboard hero, dark regional map, two-column property cards and club footer.
Small research-only additions remain in `property-research.css`. Public pages,
shared CSS, the Worker, secrets and the 20-acre/flat-land/arena-first brief are not
changed. Card maps use lazy initialization and are disposed on filtering; map
attribution remains visible.

## Why nothing appeared to update

The report examined for run 35647907725 contains 0 new rows, 0 changed rows and
0 listing pages checked. Both configured broker pages returned no listing links.
No current property data was obtained; a successful job/report publication must
not be described as successful property discovery. This change does NOT fix
source coverage or seed invented properties. Existing listing dates stay intact.

The UI also hid same-day changes by displaying only a calendar date. It now shows
check times including seconds and Eastern timezone, a separate results-loaded
time, the report/run ID, and explicit new/changed/checked counts. Missing counts
are unknown, never zero. Zero collection is distinguished from unchanged checked
listings and from outright source failure. Reload Results produces immediate
feedback and does not start a new source check. It tries current GitHub Contents
before labeled fallbacks; older CDN results cannot replace newer loaded reports.
Refresh completion still requires the exact requested run's published snapshot.

The default view is now **All tracked — includes archive** rather than an empty
active-only screen. Outside-brief records are prominently labeled, counts and
scope text distinguish them from leads, and the In-brief filter remains. No
requirements were relaxed and historical scores do not qualify sites.

## Tests and release

`tests/property-research-outcome.test.cjs` covers same-day times, unknown/zero
counts, blocked reports, exact theme imports and report ordering. The browser
smoke uses real checked-in HTML/CSS/JS, with mocked external services. It checks
original computed theme values, navigation, desktop/mobile layout, filtering,
XSS escaping, local saves, failed dispatch, same-report reload feedback, exact
run-ID handoff, and preventing stale-report rollback. Test results must be
checked in CI; this document is not a claim they have run.

The release check derives the expected release from the source, verifies live
asset hashes against the commit, and separately tests preflight/dispatch. It does
not treat successful dispatch as evidence of new properties. New property
collection remains limited until a source actually yields usable listings.
