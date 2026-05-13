# Engineering, UI/UX, and Responsive Quality Standards

Use this checklist before shipping changes to the Charlotte Polo Club site. The goal is polished, investor-grade work that is simple to maintain and feels intentional on every device.

## Engineering quality

- Make the smallest durable change that solves the user problem without adding unnecessary abstractions.
- Keep browser-delivered code free of private credentials, owner-only implementation details, or internal operational notes.
- Prefer clear names, straightforward control flow, and reusable helpers over clever one-off logic.
- Preserve existing behavior unless the request explicitly changes it.
- Treat data files as user-facing product surfaces: keep schemas stable, validate assumptions, and make fallback states understandable.
- Avoid brittle assumptions about third-party URLs when a reliable address, source name, or listing identifier can still support manual verification.
- Keep comments and docs focused on why a decision exists, not on obvious syntax.
- Run relevant local checks after every code change and document any environment limitations.

## Investor dashboard standards

- Keep investor-facing copy high level, concise, and confidence-building.
- Explain what the viewer can trust, what still needs verification, and what action the interface is taking.
- Do not expose private implementation details such as credentials, git mechanics, or internal deployment plumbing in visible page copy.
- Be precise about refresh behavior: if a button starts an agent, describe it as an on-demand or prompted refresh rather than a daily automatic refresh.
- Exact listing links are preferred, but property cards should remain useful when they contain a searchable address for the relevant broker, land, or listing platform.
- Make diligence language practical and investor-relevant: acreage, price, location, drive time, source access, verification status, and next step.

## UI/UX quality

- Prioritize visual hierarchy: clear section labels, strong headings, short supporting copy, and obvious primary actions.
- Align split-section copy deliberately; avoid awkward right-aligned paragraphs unless there is a strong design reason.
- Keep card content scannable with consistent labels, spacing, and action placement.
- Write interface copy in plain language and remove unnecessary technical terms.
- Ensure empty, loading, success, and error states tell users what happened and what to do next.
- Maintain accessible color contrast, visible focus states, semantic buttons/links, and useful `aria` labels where needed.
- Avoid layout shifts that make controls jump while data loads.

## Mobile and web optimization

- Design mobile-first fallbacks for every desktop grid, split header, and card layout.
- Use fluid sizing (`clamp`, flexible grids, wrapping actions) so content remains readable between breakpoints.
- Keep tap targets comfortably sized and avoid horizontally overflowing text or buttons.
- Make long property names, addresses, URLs, and notes wrap cleanly.
- Optimize perceived speed by keeping static pages lightweight and limiting third-party dependencies to those that directly support the product.
- Test at common widths: small mobile, large mobile, tablet, laptop, and wide desktop.
- For visible web-app changes, capture a screenshot when the environment allows it.

## Pre-ship checklist

- The requested product behavior is present.
- Copy is accurate, high level, and free of private implementation details.
- The layout works on desktop and mobile without awkward alignment.
- Data fallbacks are explicit and useful.
- Relevant tests or syntax checks pass, or limitations are clearly documented.
