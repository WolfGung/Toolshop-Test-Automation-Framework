# 4. Test design — contact form

The contact form is the smallest feature with a full set of rules, so it is
written out here as a worked example of how cases are derived.

## Rules observed

| Field | Rule |
| --- | --- |
| First name | Required |
| Last name | Required |
| Email | Required, must be a syntactically valid address |
| Subject | Required, chosen from a fixed list |
| Message | Required, minimum 50 characters |
| Attachment | Optional |

Validation runs on submit. Nothing is sent while any rule fails.

## Equivalence classes and boundaries

`message` is the only field with a numeric boundary, at 50 characters:

| Class | Value | Expected |
| --- | --- | --- |
| Below boundary | 49 characters | Rejected, "Message must be minimal 50 characters" |
| At boundary | exactly 50 | Accepted |
| Above boundary | 51+ | Accepted |
| Empty | "" | Rejected, "Message is required" |

`email` is split into valid and invalid syntax rather than enumerated, and the
invalid class is sampled at its distinct failure shapes: no `@`, no domain, no
local part, no symbol at all.

## Cases

| ID | Case | Type | Automated |
| --- | --- | --- | --- |
| TC-01 | Empty form reports all five required fields | Negative | `test_empty_form_reports_all_required_fields` |
| TC-02 | Malformed email rejected (4 variants) | Negative | `test_invalid_email_is_rejected` |
| TC-03 | Message of 49 characters rejected | Boundary | `test_message_just_below_minimum` |
| TC-04 | Message of exactly 50 characters accepted | Boundary | `test_message_at_minimum` |
| TC-05 | Complete form posts the entered values | Positive | `test_valid_submission_sends_entered_values` |
| TC-06 | Attachment of an unsupported type | Negative | Not automated — see below |

TC-06 is designed but not automated. Verifying it means uploading files to a
shared backend, and the rule it would check is not documented anywhere; it is
listed so the gap is visible rather than absent.

## Why TC-05 asserts the payload

Asserting that a success banner appears proves the frontend is satisfied. It
does not prove the right data left the browser. Intercepting the request and
checking the body catches the class of bug where a field is renamed, trimmed
or dropped on the way out — which is the failure users actually report.
