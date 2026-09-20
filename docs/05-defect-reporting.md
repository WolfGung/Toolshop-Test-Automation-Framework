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
