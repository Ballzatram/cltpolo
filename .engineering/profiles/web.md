# Web and UI profile

Extends UX-01, SEC-03, TEST-01/02 and DOC-01.

- MUST define supported browsers, viewport/device behavior and critical journeys. Test navigation, forms, loading, empty, error, permission-denied and offline states where relevant.
- MUST target WCAG 2.2 AA for web interfaces as internal policy: semantic structure, labels, keyboard operation, visible focus, contrast, error announcements, zoom and reduced motion. Automated accessibility scans are partial evidence; include keyboard and assistive-technology checks appropriate to impact.
- MUST enforce access on the server; hiding a button is insufficient. Prevent injection and unsafe rendering; apply session/cookie, CSRF and CORS rules appropriate to the authentication design.
- MUST prevent secrets in browser bundles and avoid unnecessary personal-data exposure or analytics. Document consent/retention choices where applicable.
- MUST include component/integration tests and representative end-to-end journeys. Test user-visible behavior and stable accessible locators; avoid arbitrary sleeps and CSS-class assertions.
- MUST define asset/performance budgets for meaningful user experience and measure representative pages. Verify routing, caching and deployment fallbacks.

Evidence includes browser runs, accessibility review, denied-action tests and representative performance measurements. A visual screenshot alone does not establish functional completion.
