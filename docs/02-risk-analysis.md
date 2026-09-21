# 2. Risk analysis

Risks are scored by impact on the business if the behaviour breaks, and by
likelihood of it breaking given how the feature is built. The score drives
what gets automated first and what runs on every deploy.

| # | Risk | Impact | Likelihood | Priority | Covered by |
| --- | --- | --- | --- | --- | --- |
| 1 | Wrong price or total shown at checkout | High | Medium | **Critical** | `test_cart.py`, `test_guest_checkout.py` |
| 2 | Add to cart silently fails | High | Medium | **Critical** | `test_cart.py::test_add_product_to_cart` |
| 3 | Checkout cannot be completed by a guest | High | Low | **High** | `test_guest_checkout.py` |
| 4 | Catalog renders empty or partially | High | Low | **High** | `test_catalog.py`, `test_products_api.py` |
| 5 | Search returns unrelated or no results | Medium | Medium | **High** | `test_search.py`, `test_search_api.py` |
| 6 | Contact form accepts invalid data or drops valid data | Medium | Medium | **High** | `test_contact_form.py` |
| 7 | Sorting does not reorder the grid | Medium | Medium | Medium | `test_catalog.py` |
| 8 | Pagination repeats or skips products | Medium | Low | Medium | `test_products_api.py::test_pagination_pages_do_not_overlap` |
| 9 | Price filter returns products outside the range | Medium | Low | Medium | `test_products_api.py::test_price_filter_respects_bounds` |
| 10 | API returns a success body for an unknown id | Low | Medium | Low | `test_products_api.py::test_unknown_product_id` |
| 11 | User input reflected back as markup | High | Low | Medium | `test_search_api.py::test_search_does_not_reflect_markup` |

## What the scoring changes

- The `smoke` set is every risk rated High or Critical, and nothing else:
  risks 1 to 6, each covered at the layer that shows the failure soonest —
  the cart and the guest flow for 1 and 2, the guest flow again for 3, the
  catalogue in a browser and the first page of products over the API for 4,
  search at both layers for 5, and the contact form's two validation paths
  for 6. If one of them fails, running the rest wastes the pipeline's time.
- Risks 7 to 11 are Medium or Low and stay out of that set. A smoke set that
  covers everything gates nothing, and the full suite runs on every push in
  any case.
- Risks 7–10 are cheap to cover at the API level, so they are tested there
  rather than through the browser — faster, and they fail with a clearer
  cause.
- Risk 11 is a single sanity check, not a security audit. A real assessment
  belongs with tooling built for it, and is called out here rather than
  implied by one test.
