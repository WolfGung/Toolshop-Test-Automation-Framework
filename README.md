# Toolshop — Quality Engineering Project

A complete quality cycle for a web application, from reading an undocumented
product to a maintained automated suite: scope and requirement gaps, a
risk-ranked strategy, test design, and 32 automated cases across API, UI and
end-to-end layers.

**Application under test:** [practicesoftwaretesting.com](https://practicesoftwaretesting.com)
— a public demo storefront with a REST API, published as a practice target for
test automation. No employer code, data or systems are involved.

## Why this repository exists

Most automation portfolios show a folder of tests. The harder part of the job
happens before the first test is written: deciding what is worth covering,
at which layer, and what is deliberately left out. That reasoning is written
down here and each decision is traceable to the test that implements it.

| Document | Question it answers |
| --- | --- |
| [Scope and requirements](docs/01-scope-and-requirements.md) | What is under test, what is not, and which rules had to be derived because nothing documents them |
| [Risk analysis](docs/02-risk-analysis.md) | What breaks the business if it fails, and what that changes about coverage |
| [Test strategy](docs/03-test-strategy.md) | Which layer each check belongs at, and how a shared environment shapes the design |
| [Test design](docs/04-test-design-contact-form.md) | A worked example: equivalence classes and boundaries for one feature |
| [Defect reporting](docs/05-defect-reporting.md) | The template, plus a finding that was verified and closed rather than filed |

## Coverage

| Layer | Cases | Focus |
| --- | --- | --- |
| API | 11 | Pagination, schema, search, price filtering, error codes |
| UI | 19 | Catalog rendering, sorting, search, cart arithmetic, form validation |
| E2E | 2 | Guest checkout through to payment selection |

10 of these carry the `smoke` marker and cover the critical risks.

## Stack

Python 3.11+ · Pytest · Playwright · httpx · Allure · Docker · GitHub Actions

## Architecture

```
src/toolshop/
  config.py          environment-driven settings
  api/               HTTP client and resource helpers
  data/factories.py  per-run test data
  ui/pages/          Page Object Model
tests/
  api/               API-only checks
  ui/                browser checks
  e2e/               full business flows
  conftest.py        fixtures, request interception, failure artefacts
docs/                the reasoning behind all of the above
```

Three decisions worth calling out:

**Locators are the application's own `data-test` attributes.** They are part
of the markup contract, so a copy change or a restyle does not turn into a
suite-wide failure.

**There are no fixed sleeps.** Sorting, searching and filtering refetch the
product grid; the suite waits for that response and then for the grid to
actually re-render, using a fingerprint of the rendered names. Waiting on the
response alone still races the render.

**Writes to the shared backend are intercepted by default.** The application
is public and used by other people. Contact form submissions are fulfilled in
the browser and the payload is asserted instead of being sent — which also
catches the bug class where a field is renamed or dropped on the way out. The
one test that places a real order is deselected by default.

## Running the suite

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

pytest                 # everything except tests that write data
pytest -m smoke        # the critical set
pytest -m api          # no browser needed, runs in seconds
pytest -m "ui or e2e"  # browser tests
pytest --headed        # watch it run
```

`make install`, `make smoke`, `make api`, `make report` wrap the same commands.

### Configuration

Copy `.env.example` to `.env` to override any of:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BASE_URL` | `https://practicesoftwaretesting.com` | Storefront |
| `API_BASE_URL` | `https://api.practicesoftwaretesting.com` | REST API |
| `HEADLESS` | `true` | Browser visibility |
| `SLOW_MO` | `0` | Milliseconds between actions, for debugging |
| `TIMEOUT_MS` | `30000` | Default wait for UI assertions |
| `MOCK_CONTACT_API` | `true` | Intercept writes instead of sending them |

The browser engine is chosen with `pytest --browser firefox` (or `webkit`).

### Opting into tests that write data

```bash
pytest -m creates_data
```

This places a real order on the shared demo backend. Run it deliberately.

## Reporting

Every run writes to `allure-results/`. A failing test attaches a full-page
screenshot, the page HTML, the URL and any console errors, so a red build in
CI can be diagnosed without reproducing it locally.

```bash
allure serve allure-results
```

Failures are grouped by `allure/categories.json` into product defects,
timeouts, selector drift and infrastructure problems — the distinction that
decides who picks the failure up.

## Docker

```bash
docker compose run --rm tests              # smoke by default
docker compose run --rm tests pytest -m api
```

## CI

`.github/workflows/tests.yml` runs API tests first, then browser tests, on
every pull request and nightly. Browser tests get one rerun on failure; a test
that only passes on the rerun is still reported as flaky rather than hidden.
Allure results are uploaded as artefacts on every run, including failures.
