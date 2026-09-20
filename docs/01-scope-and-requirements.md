# 1. Scope and requirements

## Application under test

Toolshop — a demo e-commerce storefront published at
`https://practicesoftwaretesting.com` with a public REST API at
`https://api.practicesoftwaretesting.com`. It is maintained as a practice
target for test automation, so it can be exercised without affecting anyone's
production system.

Architecture relevant to testing:

| Layer | Detail |
| --- | --- |
| Frontend | Single-page application, client-side routing and validation |
| Backend | REST API, JSON, paginated collection endpoints |
| State | Cart held client-side until checkout; orders written server-side |
| Test hooks | Every interactive element carries a `data-test` attribute |

## In scope

- Catalog: product grid, sorting, search, product detail
- Cart: add, change quantity, remove, totals
- Checkout: guest path up to and including payment selection
- Contact form: field validation and submission payload
- Public API: products, search, brands, categories, pagination, price filter

## Out of scope, and why

| Area | Reason |
| --- | --- |
| Registered-user flows, favourites, invoices | Require creating accounts on a shared backend |
| Admin panel | Needs privileged credentials that are not mine to use |
| Payment processing | No real payment provider is wired up |
| Performance and load | Shared environment; load testing it would affect other users |
| Cross-browser matrix | Chromium in CI; the suite is engine-agnostic and runs on Firefox and WebKit via `--browser` |

## Requirement gaps found while reading the application

Working without a specification, the rules below were derived from observed
behaviour. Each one is a question a real product owner would need to answer,
and each is pinned down by a test so a change in behaviour surfaces as a
failure rather than as a surprise.

| # | Observed rule | Open question |
| --- | --- | --- |
| R1 | Contact message must be at least 50 characters | Is 50 a product decision or an implementation detail? No maximum is stated. |
| R2 | Validation messages appear only on submit, not on blur | Intended, or an accessibility gap? |
| R3 | Product grid is fixed at nine items per page | Should the page size be configurable? |
| R4 | Search matches name and description, with no relevance ordering | Is substring matching sufficient for the catalog's size? |
| R5 | Cart survives navigation but is not tied to an account | Expected lifetime of an abandoned cart is unspecified. |
