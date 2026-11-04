# UI Behavior Contract

## Route and session behavior

- Routes: login, overview, codebase, document ingestion, Q&A, and metadata settings.
- Protected workspace routes require only the UI demo session. A missing session redirects to login; a valid tab session survives refresh; logout clears it.
- Label the interface as an experimental/demo environment. It does not authenticate to backend services.

## Mode behavior

- Initial mode is Demo. The active mode is visible on every workspace operation and result.
- Demo calls fixture adapters only and makes no operational service/model request. Every fixture outcome is labeled simulated and not written to a backend.
- API mode calls only a per-operation adapter that passed its service contract/readiness gates. An API failure remains a failure/blocker and never calls a fixture.
- Disable mode switch and repeated submission while an operation is pending. After a mode switch, clear transient results/history; retain metadata definitions.

## Metadata and form behavior

- Form controls derive from validated definitions. Keys and option values are stable English identifiers; labels are Persian.
- Document metadata, descriptive user values, and fixed service fields are separate models.
- Hidden/disabled fields and unset values are excluded. Numeric `0` and boolean `false` are supplied values.
- Query filters use equality for a single value, any-of for multiple values, and AND between fields. They are UI intent only unless an API contract confirms enforcement.
- Browser persistence failure yields a warning and in-memory behavior; do not display a saved confirmation.

## Results and diagnostics

- Demo and API results have separate provenance and visually distinguishable labels.
- API success reflects an actual successful response only. Display only supplied citations, identifiers, statuses, counts, and logs.
- Show intended and transmitted payloads separately when a reduced API request is offered. Sanitize responses and errors; never expose credentials, tokens, provider secrets, or stack traces.
- Distinguish unavailable service, authorization failure, invalid input, timeout/uncertain completion, provider failure, and no evidence.

## Localization and accessibility

- Persian and RTL are the default presentation. Technical identifiers, paths, code, and JSON use LTR direction without disrupting surrounding Persian text.
- Controls have visible Persian labels, keyboard operation, and visible focus; status is not conveyed by color alone.
- At 1366×768, the page has no horizontal overflow; at 390px, navigation and main actions remain available. Code/JSON diagnostics may scroll internally.
