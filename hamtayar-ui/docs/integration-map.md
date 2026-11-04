# Integration evidence — 2026-11-04

Repository inspected: `fnaeiji/hamtayar-suite`, base commit `9ed3f44e941b93572f8b62f59c1598853fe9fd8c`.
All implementation changes are confined to `hamtayar-ui`. No backend, database,
authentication, CGC workflow, or network exposure was changed.

| Operation                | Classification | Evidence / current blocker                                                                                                                                                    |
| ------------------------ | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Document Demo            | Demo only      | Local fixed fixture, no reading/extraction/indexing of selected files or operational requests                                                                                 |
| Q&A Demo                 | Demo only      | Fixed answer and example sources, independent of question and metadata                                                                                                        |
| Codebase Demo            | Demo only      | Local sample log sequence; no archive extraction or graph construction                                                                                                        |
| Hamtayar document client | Adapter only   | Exact multipart mapping and runtime response validation tested against mocked transport; no configured live target, deployed limit, CORS or executor verification             |
| Hamtayar Q&A             | Blocked        | Source authentication dependency unconditionally returns 401. Question-only adapter has mocked contract tests; it is not live integration                                     |
| CGC API                  | Blocked        | No running OpenAPI/capabilities/diagnostics available, limits and executable/two-Neo4j readiness unverified. Local-only guard implemented; no upload/polling adapter invented |

## Verified source contracts

- `hamtayar/apps/document_ingestion/api/schemas/jobs.py`: multipart fixed fields
  `file`, `source_id`, `knowledge_space_id`, `version`, `processing_profile`.
  Completed response: `status`, `source_id`, `version`, nullable `chunks_indexed`,
  optional nullable `request_id`. The UI displays null as «گزارش نشده».
- `hamtayar/apps/retrieval/api/schemas/answers.py`: JSON `{question}` only;
  trimmed question 1–4096 Unicode code points, no NUL. Response status
  `completed` or `no_evidence`, answer, citation identifiers, request ID.
- `hamtayar/apps/retrieval/api/dependencies.py`: trusted auth not yet implemented;
  401 is a blocker, and missing executor returns 503. Demo login is never sent.
- Existing UI `specs/001-hamtayar-demo-ui/contracts/cgc-local-api.md` is a candidate
  contract, not proof of current CGC runtime capability. No live CGC requests were made.

## Gates before enabling API actions

Configuration is not evidence of readiness. `hamtayarReadiness` deliberately
returns blocked in this delivery. `.env.local` alone does not turn on uploads.
The adapter can be exercised independently with mocked tests.

For a future live connection, record the exact deployed version/base URL, verified
schema and per-service byte limit, browser CORS or approved same-origin proxy,
executor readiness, timeouts and trusted authentication. Then update the readiness
function for that operation with that evidence and run the controlled live tests.
Never introduce a browser secret or bypass backend authorization to satisfy a gate.

For CGC also inspect current capability/diagnostic output, archive limits and types,
endpoint sequence, returned IDs, status/log/cancellation semantics, executable
readiness, staging and destination Neo4j, and a controlled complete operation.
Only an explicit loopback URL is eligible; do not proxy CGC to a public network.

## Wire boundaries and errors

Custom document metadata is never appended to multipart data. The reduced test
requires explicit confirmation. Q&A only sends the trimmed question, never user
metadata, filters, demo credentials or arbitrary database syntax. Filters remain a
structured UI model with equality, any-of and AND, not SQL/Cypher.

Transport omits credentials, applies an abortable timeout, and discards raw error
bodies. 401, 413, 422, 429, 500, 503, 504, network loss and timeout have separate
messages. Upload network loss/timeout or invalid success responses remain uncertain;
no automatic retry or service-side cancellation claim is made. IDs are retained.
Diagnostics only consume mapped DTOs and redact sensitive field names recursively.

## Deferred external work

Trusted Padeen authentication, real Q&A execution, custom metadata ingestion,
backend-enforced retrieval filters, parser readiness and CGC integration remain
external dependencies. No operation is classified as **Connected and tested**.

## Current UI revision

«همتایار کد» is now a direct browser navigation to the existing HamtayarDemo
frontend (default loopback port 5173), not the earlier code fixture or a CGC API
integration. Main UI uses strict dev port 5174. The link does not start services or
establish their readiness. A launch-help route remains at `/codebase`.
Document/Q&A UI metadata is restricted to `center` and `document_type`; descriptive
`person_access_level` is not an ACL and never bypasses backend authentication.

Latest profile: prompt access-level select maps the shared classification value to
intended document_type equality; only center and access-level controls are shown.
Center choices are session-only successful Demo registration records, not a backend
center catalog. Existing question-only wire DTO and blocked API gates are unchanged.
