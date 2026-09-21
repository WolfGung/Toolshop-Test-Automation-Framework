# 5. Defect reporting

## Template

```
ID / Title
Severity · Priority · Component · Environment
Preconditions
Steps to reproduce
Actual result
Expected result
Impact on the user
Evidence (screenshot, request/response, console)
Notes
```

## Worked example — a finding that was closed, not filed

Filing a defect that turns out not to exist costs a developer an hour and
costs the reporter credibility. This is the check that happens before a report
is written, shown end to end.

**Observation.** Submitting the empty contact form renders five validation
messages. Focus stays on the Send button afterwards. The initial hypothesis
was that a screen-reader user gets no indication the submission failed.

**Verification.** Inspected the rendered container rather than trusting the
hypothesis:

```
id=message_alert
data-test=message-error
role=alert
class=alert alert-danger mt-3 p-2
```

**Outcome — not a defect.** `role="alert"` makes the container a live region,
so its contents are announced when it appears. Focus staying on the submit
button is standard for this pattern. No report filed.

**What it changed instead.** The page object now locates validation messages
through `data-test="message-error"` rather than the `.alert-danger` CSS class,
because the former is a stable contract and the latter is styling.

## Worked example — an open question, raised as a question

**Observation.** Validation runs on submit only. Focusing a required field and
leaving it empty produces no message until Send is pressed.

**Why it is not filed as a defect.** Both behaviours are common and defensible;
which one is correct is a product decision, not a bug. It is recorded in
[requirement gaps](01-scope-and-requirements.md#requirement-gaps-found-while-reading-the-application)
as R2 so it reaches whoever owns that decision.

**Severity if it were filed:** Low, usability.

## Worked example — a race mistaken for a pricing defect

`test_update_quantity_in_cart` failed reading `$14.15` where `$28.30` was
expected after raising a line's quantity from 1 to 2. Read from the error
message alone, that looks like the application charging for one unit while
billing for two — a serious, headline-worthy defect. It was not filed on
that reading; here is the check that ran first.

**Observation.** Immediately after `product-quantity.fill("2")` and a Tab
press, `cart-total` still read the pre-change figure. Reloading the page
showed the correct, doubled total, which ruled out a server-side arithmetic
error but did not yet explain the live read.

**Verification.** Polled both figures on the running page every 20ms rather
than trusting a single read after the fact:

```
t=0.042s line-price='$28.30' cart-total='$14.15'
t=0.258s line-price='$28.30' cart-total='$28.30'
```

and the network log for the same interaction:

```
PUT /carts/{id}/product/quantity  {"product_id": "...", "quantity": 2}  -> 200
GET /carts/{id}                                                          -> 200
```

`line-price` is computed client-side the instant the field blurs — before
the server has agreed to anything. `cart-total` only follows once the PUT
round-trips and the cart is refetched, roughly 200ms later on this stand.
The failing test read `cart-total` in the gap between those two moments.

**Outcome — not a defect.** The application always arrives at the correct,
server-confirmed total; it just takes one network round trip to get there,
which is ordinary for an async update. No report filed.

**What it changed instead.** `CartPage.set_quantity` now waits for
`cart-total` itself to change before returning, the same pattern
`ProductPage.add_to_cart` already uses for the cart badge, rather than
returning as soon as the keystroke was accepted.

## Worked example — a wait keyed on a verb the application stopped using

Three search and sorting tests failed together, each one timing out while
waiting for the product grid. A grid that never arrives is risk 4 in
[the risk analysis](02-risk-analysis.md) — "catalog renders empty or
partially", rated High — so this cluster looked the most like a real defect
of the four found in the same pass.

**Observation.** The catalog rendered perfectly in a headed run. The suite
still timed out: `HomePage.wait_for_products` waited on a `GET` response
under `/products`, and no such response ever came.

**Verification.** Drove the storefront with Playwright and logged every
request the page issued while searching:

```
QUERY http://localhost:8091/products/search   -> 200
QUERY http://localhost:8091/products          -> 200
```

The application had moved the product list off `GET` and onto the HTTP
`QUERY` method — a method with a body, standardised for exactly this case, a
read whose parameters are too large or too structured for a URL. The
response bodies were unchanged.

**Outcome — not a defect.** Nothing about the product is broken; the request
the suite was waiting for simply no longer exists. Filing this would have
been a report about our own assumption.

**What it changed instead.** `_is_product_list_response` now recognises the
response by what it carries, a paginated `data` list under `/products`,
without asserting the method. The verb is not part of what these browser
tests prove, so the next change of that kind cannot break them. The endpoint
still answers `GET` as well, which is how the API suite keeps asking for the
same page of products and getting it.

## Note — the other two clusters diagnosed in this pass were also drift, not defects

The guest-checkout and contact-form failures investigated alongside the cart
race and the search timeouts (2026-09-21) had the same shape: the required
behaviour was still present, reachable through markup or a flow step the page
objects had not been updated for.

- **Guest checkout.** "Continue as Guest" is now a tab next to "Sign in" (the
  tab that is active by default), so `guest-email` existed in the DOM but was
  hidden until the tab was selected. Submitting the guest panel then revealed
  a separate `proceed-2-guest` control that advances the wizard to the
  address step; the form submit alone did not. Confirmed live, both steps
  restore the full guest flow through to an enabled "finish" button — fixed
  in `CheckoutPage.continue_as_guest`.
- **Contact form.** Validation used to nest every message as a `<div>` inside
  one `data-test="message-error"` container; it now renders one independent
  `alert-danger` banner per invalid field (`first-name-error`,
  `last-name-error`, `email-error`, `subject-error`, `message-error`), each
  its own live region. All five still render, in field order, on an empty
  submission — fixed in `ContactPage.errors`.

No test in either cluster needed its assertion weakened; each page object was
updated to reach the same fact through the application's current markup or
flow.
