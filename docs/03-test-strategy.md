# 3. Test strategy

## Where each check lives

A check belongs at the lowest layer that can still prove the thing that
matters. Business rules about data — pagination, filtering, schema, error
codes — are verified against the API, where a failure names its own cause.
Only behaviour that a user can actually see is driven through a browser.

| Layer | Cases | What it proves |
| --- | --- | --- |
| API | 11 | Data contracts, pagination, filtering, error handling |
| UI | 19 | Rendering, search, validation, cart arithmetic |
| E2E | 2 | The guest purchase path holds together |

31 cases run by default; the 32nd places an order and is opt in.

## Test selection

| Marker | Purpose | When to run |
| --- | --- | --- |
| `smoke` | The critical risks from the risk analysis | Every deploy, every pull request |
| `api` | API-only, no browser | On every push; fastest feedback |
| `ui` | Browser tests | Pull requests and nightly |
| `e2e` | Full flows | Pull requests and nightly |
| `negative`, `boundary` | Invalid input and limits | Full suite |
| `creates_data` | Writes to the shared backend | Opt in explicitly |

## Handling a shared environment

The application is public and used by other people at the same time. That
shapes three decisions:

1. **Test data is generated per run.** Email addresses and customer records
   carry a random suffix, so two runs never collide.
2. **Writes are intercepted by default.** Contact form submissions are
   fulfilled in the browser and the payload is asserted instead of being sent.
   `MOCK_CONTACT_API=false` exercises the real endpoint when that is the point
   of the run.
3. **Order placement is opt in.** The one test that creates an order is
   deselected by default.

## Stability

- Locators use the application's own `data-test` attributes, not text or CSS
  paths.
- There are no fixed sleeps. Actions that refetch the product grid wait for
  the response and then for the grid to actually re-render.
- Tests are independent: each one starts from a fresh browser context and
  builds the state it needs.
- Reruns are set to 1 in CI only, and a rerun that passes is still reported as
  a flaky test rather than hidden.

## Running against an environment that blocks automation

The hosted storefront returns HTTP 403 to data-centre IP ranges, which
includes GitHub-hosted runners. This is worth stating plainly because of how
it shapes the pipeline:

- The gate is the whole suite run against a stand the pipeline starts itself,
  where a failure is always about the code.
- Against the hosted site, the browser suite is gated behind a reachability
  probe and skipped, with a notice, when the storefront cannot be reached. A
  skipped job is the honest outcome; 21 red tests would report a product
  failure that did not happen.
- Browser tests are run locally, and on a self-hosted runner if this were a
  real project.

Which check runs in which environment, what each environment is allowed to do,
and how to read a skip is the subject of
[Environments and CI](06-environments-and-ci.md).

The page objects were changed to make this diagnosable: they wait for the
application shell and, on failure, report the navigation status and what
`app-root` actually contained. The first version of the suite reported the
same situation as "locator a.card not found", which pointed at a selector bug
that did not exist.

## What this strategy does not cover

Accessibility, performance, security beyond one reflection check, and
cross-browser rendering. Each needs its own tooling and its own time budget;
listing them here is more honest than a green suite that implies they were
considered.
