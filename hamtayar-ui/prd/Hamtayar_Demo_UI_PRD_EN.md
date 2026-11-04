# Hamtayar Demo UI — Product Requirements Document

- Feature key: `hamtayar-demo-ui`
- Version: 1.0
- Date: 2026-11-04
- Status: Ready for specification and planning; implementation has not been verified
- Product: Hamtayar
- Document language: English
- UI and end-user README language: Persian
- Intended use: Input to Spec Kit's `specify` stage. This PRD does not replace the generated `spec.md`, `plan.md`, or `tasks.md`.

## 1. Problem and desired outcome

Hamtayar's document ingestion and retrieval capabilities are being developed in a Python backend, with workflow orchestration under `apps`. A separate CGC/HamtayarDemo project may provide codebase processing. The team needs a shared visual surface to demonstrate these capabilities, enter test data, and inspect available API results without building the final product frontend.

Deliver a lightweight, runnable dashboard in `Hamtayar/hamtayar-ui`, beside the existing `Hamtayar/hamtayar` backend. It must support demonstrations without a running backend and real tests of verified, available integrations. It must make the difference between these modes unmistakable.

## 2. Goals and non-goals

### Goals

- Provide a presentable Persian RTL dashboard for Codebase, Document Ingestion, and Q&A.
- Allow entry through one fixed demo account.
- Let the operator manually configure metadata fields and enter per-document metadata, descriptive user information, and query filters.
- Make each supported request and its result inspectable.
- Connect to existing APIs where their actual contracts and dependencies permit it.
- Keep future replacement of local authentication and metadata configuration straightforward.

### Explicit non-goals

- Production authentication, Padeen integration, identity verification, roles, or user administration.
- New login APIs, server-issued demo tokens, or bypassing existing backend authorization.
- A server-side metadata registry, schema governance system, settings database, or database migrations.
- Completing LangGraph workflows, implementing embedding/chunking, modifying domain retrieval filters, or creating replacement pipelines.
- Building a new code-processing engine or general CGC gateway.
- Full document management, persistent chat, real-time streaming, or production deployment.
- Automatically committing, pushing, moving repositories, or rewriting the project's constitution.

## 3. Users

| User | Need |
|---|---|
| Technical lead / presenter | Demonstrate the three product areas from one clean interface. |
| Developer / tester | Submit controlled input, inspect actual requests and responses, and identify integration gaps. |
| Observer | Understand what the demo can do and which results are simulated. |

These personas share the same demo account. They do not introduce permission roles.

## 4. Decisions already made

| Topic | Decision |
|---|---|
| Login | Frontend-only fixed account: `demo` / `Hamtayar123!`. |
| UI language | Persian, RTL; identifiers, code, paths, and JSON remain LTR. |
| Metadata configuration | Manually configured and persisted in the current browser only. |
| User information | Descriptive test input; never verified identity or access grants. |
| Demo independence | All three main pages work in Demo mode without backend services. |
| Real integration | Use verified existing contracts; unsupported features remain visibly unavailable. |
| Backend changes | Only small compatible transport-to-existing-executor mappings when the underlying capability already exists. |
| Delivery location | `hamtayar-ui` is a sibling of `hamtayar`, not a backend subdirectory. |
| Future work | Document upgrade boundaries; do not implement future infrastructure. |

## 5. Scope and priorities

P1 is required for a usable demo. P2 means integration work follows the core demo and remains in scope wherever the corresponding service is available. P2 does not authorize new backend domain development.

| Story | Priority | Independently verifiable outcome |
|---|---|---|
| US1 — Enter and navigate | P1 | Sign in, visit each workspace, refresh, and sign out without a backend. |
| US2 — Configure metadata | P1 | Add a field, use it in a form, and retain the definition after refresh. |
| US3 — Demonstrate document ingestion | P1 | Select documents with independent metadata and inspect labeled demo outcomes. |
| US4 — Demonstrate Q&A | P1 | Enter a question, user information, and filters; inspect a labeled sample answer. |
| US5 — Demonstrate codebase processing | P1 | Select an archive and inspect explicitly simulated processing states/logs. |
| US6 — Test available services | P2 | Submit real requests through verified contracts and inspect real results or precise blockers. |

## 6. Functional requirements

### 6.1 Login and navigation

- **FR-001:** Accept only the fixed demo credentials. Invalid input must leave the user on the login page with a clear Persian error.
- **FR-002:** Preserve the signed-in UI state across refresh within the browser tab session. Logout must remove it and return to login. Do not persist the password.
- **FR-003:** Dashboard routes require the demo UI session. Clearly label login and dashboard as “محیط آزمایشی”. This is a presentation gate, not security enforcement.
- **FR-004:** Provide Overview, Codebase, Document Ingestion, Q&A, Metadata Settings, and Logout navigation. The overview contains the three workspace cards and accurately labeled connection information.
- **FR-005:** Every workspace exposes appropriate empty, loading, success, and failure states. Do not fabricate operational counts or success rates.

### 6.2 Demo and API modes

- **FR-006:** Provide an explicit Demo/API selection. Default to Demo for first launch. Keep the active mode visible on every operation and result.
- **FR-007:** Demo mode must use local fixtures and send no operational requests to Hamtayar, CGC, databases, or model providers. It must display “نمایشی؛ داده‌ای در بک‌اند ثبت نمی‌شود”.
- **FR-008:** API mode must report success only from actual API responses. An API failure must never trigger a silent fallback to fixtures.
- **FR-009:** Disallow mode switching while an operation is pending. When switching afterward, clear transient results and mode-specific histories to avoid mixing simulated and actual outcomes. Retain metadata definitions.
- **FR-010:** A reachable health endpoint must not be labeled as proof that an ingestion/answer workflow is operational. Show service reachability and operation availability separately.

### 6.3 Local metadata configuration

- **FR-011:** Maintain document and descriptive-user field definitions locally. Derive query-filter controls from document fields marked filterable.
- **FR-012:** Each definition supports a unique English key, Persian label, document/user group, type, options where applicable, required flag, enabled flag, form visibility, and document filterability.
- **FR-013:** Support `text`, `number`, `boolean`, `select`, and `multi_select`. Validate type, required values, and option membership. Numeric zero and boolean false are valid supplied values.
- **FR-014:** Support add, edit, delete, and restore defaults. Warn before deleting/changing a definition in a way that discards entered values. Duplicate keys and invalid option definitions must be rejected.
- **FR-015:** Persist definitions across refresh and browser restart in the current browser. Explain their local-only nature. If browser persistence fails, show a warning and allow temporary in-memory use; do not falsely claim the settings were saved.
- **FR-016:** Forms must update from definitions without a code change. Required document fields do not automatically become required query filters. Disabled or hidden fields must not silently contribute stale values to submissions.
- **FR-017:** Reject reserved security and system keys, including `tenant_id`, `acl_principals`, `principals`, `access_scope`, and `subject_id`. Keep fixed endpoint fields separate from custom metadata.
- **FR-018:** Seed the fields in the following table. Technical option values remain stable English identifiers; display labels are Persian.

| Key | Group | Type | Persian label / sample options |
|---|---|---|---|
| department | document | select | واحد سازمانی; engineering=فنی, hr=منابع انسانی, finance=مالی |
| project | document | text | پروژه |
| document_type | document | select | نوع سند; guide=راهنما, report=گزارش, policy=آیین‌نامه |
| tags | document | multi_select | برچسب‌ها; editable sample tags |
| display_name | user | text | نام نمایشی کاربر |
| expertise | user | text | تخصص کاربر |
| answer_language | user | select | زبان پاسخ; fa=فارسی, en=انگلیسی |

### 6.4 Document ingestion

- **FR-019:** Provide drag-and-drop and file selection for multiple documents. Display filename, type, and size per file. Send separate requests and show independent outcomes; one failure must not erase another file's success.
- **FR-020:** Each file has editable `source_id` with a suggested UUID, `knowledge_space_id`, `version`, `processing_profile`, and independent custom metadata. Support applying shared values with per-file overrides.
- **FR-021:** Provide Preview request, Submit, and Clear form. Validate required values and confirmed format/size limits before submission. Do not infer parser readiness solely from the HTTP format allowlist.
- **FR-022:** Show the intended data and the actual transmitted data separately whenever the backend cannot accept custom metadata. Require an explicit upload-without-custom-metadata choice before omitting entered metadata. Otherwise block that real submission with an explanation.
- **FR-023:** Display only observable real states and fields in API mode. Do not invent workflow nodes, processing percentages, jobs, or polling endpoints. A missing/null chunk count displays “گزارش نشده”, not zero.
- **FR-024:** Prevent duplicate submissions and automatic ingestion retries. A timeout or connection loss must indicate an uncertain server outcome, not guaranteed cancellation. Preserve the file's source identity for a deliberate retry.

### 6.5 Q&A

- **FR-025:** Provide question input, descriptive-user fields, document filters, Submit, an answer area, and sources. Preserve the user's input on validation or API failure.
- **FR-026:** Query filters support equality for a single value, any-of for multiple selections, and AND between different fields. An unset filter is omitted; zero and false are not treated as unset. Reject arbitrary database query syntax.
- **FR-027:** Preview an internal model containing `question`, `user_metadata`, and `filters`. These are UI names, not a claim about the actual API contract.
- **FR-028:** If user metadata or filters cannot be accepted/applied, disclose this before submission. Only an explicit “تست فقط پرسش” action may send a question without them. Never present the resulting answer as personalized or filtered by omitted data.
- **FR-029:** Display actual answer statuses, citations, and request identifiers. Distinguish `no_evidence` from provider failure. Do not invent evidence text, links, or citations.
- **FR-030:** Render answer Markdown safely. Keep history in memory for this UI session only; do not imply multi-turn backend memory or streaming unless verified as supported.

### 6.6 Codebase

- **FR-031:** Provide archive selection, project name, upload, start processing where supported, status, and logs. Provide a complete labeled fixture demonstration when no service is available.
- **FR-032:** Locate and inspect the actual CGC/HamtayarDemo service before enabling API actions. Use its existing supported HTTP operations. Confirm archive formats, limits, identifiers, and status/log semantics.
- **FR-033:** If the service is missing or unavailable, show a disconnected/unavailable explanation. This must not disable document or Q&A pages. Do not invent routes or build a replacement service.

### 6.7 Diagnostics and integration boundaries

- **FR-034:** A collapsible Test details panel provides sanitized intended/transmitted payloads, responses, elapsed time, and request_id when supplied. Do not fabricate a server request_id for fixtures or network failures.
- **FR-035:** Show actionable Persian messages for authentication/permission failures, invalid input, upload limits, unsupported formats, rate limits, unavailable services, provider errors, timeouts, and network errors. Do not expose stack traces, passwords, tokens, or provider secrets.
- **FR-036:** Configure service addresses and timeouts outside page components. A service requiring an unavailable trusted authentication mechanism remains blocked; frontend demo login must not bypass it.
- **FR-037:** Use ready backend contracts. Only a small compatible transport mapping to an already implemented capability is permitted. Changes to domain chunks, storage payloads, retrieval filtering, or unfinished workflows are deferred and documented.
- **FR-038:** Never simulate real metadata support by silently discarding input, accepting then ignoring fields, or appending filters to the prompt as though they were enforced retrieval conditions.

## 7. Acceptance scenarios

| Scenario | Given / When / Then | Coverage |
|---|---|---|
| AC-01 | Given no backend, when valid demo credentials are entered, then the dashboard opens; invalid credentials fail; refresh retains the session; logout removes it. | US1, FR-001–004 |
| AC-02 | Given Demo mode, when all three workspaces are exercised, then labeled sample results appear and no operational service requests are sent. | US3–5, FR-006–009 |
| AC-03 | Given Metadata Settings, when a document select field is added and marked filterable, then it appears in upload and query controls without code changes and survives refresh. | US2, FR-011–018 |
| AC-04 | Given required numeric/boolean fields, when zero/false is supplied, then validation accepts them; missing required values and invalid options fail. | US2, FR-013 |
| AC-05 | Given a used field, when a destructive definition change is attempted, then the operator is warned and stale values cannot silently be submitted. | US2, FR-014–016 |
| AC-06 | Given two files with different metadata, when submitted, then their payloads and results remain independent, including a partial failure. | US3/6, FR-019–024 |
| AC-07 | Given an API without custom metadata support, when upload is attempted with metadata, then omission requires the explicit reduced test action and is visible in the transmitted preview. | US6, FR-022 |
| AC-08 | Given a question with unsupported filters/user metadata, when Submit is attempted, then the full request is blocked; only explicit question-only testing sends the reduced payload. | US4/6, FR-025–028 |
| AC-09 | Given actual completed/no_evidence/error API responses, when received, then each has a distinct UI outcome, with only supplied citations and identifiers. | US6, FR-029–030 |
| AC-10 | Given a timeout during ingestion, when the UI stops waiting, then it does not automatically resubmit or claim server cancellation. | US6, FR-024 |
| AC-11 | Given a 401 or missing executor, when an API action is attempted, then the limitation is shown without auth bypass or fixture fallback. | US6, FR-008, FR-036 |
| AC-12 | Given CGC is absent, when Codebase is opened, then its unavailable state is clear and its Demo remains usable; other workspaces still function. | US5/6, FR-031–033 |
| AC-13 | Given a response containing unsafe markup or sensitive diagnostics, when displayed, then scripts cannot execute and secrets are excluded from test details. | FR-030, FR-034–035 |
| AC-14 | Given an operation in progress, when a second submit or mode switch is attempted, then duplicate submission/mode mixing is prevented. | FR-009, FR-024 |

## 8. Quality requirements

- **NFR-001 — Usability:** Complete the main demonstration at 1366×768 without page-level horizontal scrolling; code/JSON panels may scroll internally. At 390px width, navigation and main actions remain accessible.
- **NFR-002 — Accessibility:** Form controls have labels and keyboard access; focus is visible; status is not conveyed by color alone.
- **NFR-003 — Responsiveness:** Local navigation and metadata edits visibly respond within one second on the documented test machine, excluding backend latency. Record the environment instead of making an unmeasured performance claim.
- **NFR-004 — Privacy:** Persist field definitions and the UI session only as needed. Do not persist document contents, answer history, credentials, or sensitive test inputs by default.
- **NFR-005 — Maintainability:** Real clients, fixtures, local authentication, and metadata configuration are separable so they can be replaced without rewriting pages.
- **NFR-006 — Reliability:** Backend unavailability does not prevent local Demo use. Surface local storage errors and retain usable in-memory state.

## 9. Data concepts and lifecycle

| Concept | Meaning | Persistence |
|---|---|---|
| Demo session | Frontend signed-in flag; no backend authority | Browser tab session |
| Field definition | Local form configuration | Current browser across restarts |
| Document draft | File reference, fixed request fields, metadata | In-memory until cleared/refreshed |
| User description | Manually entered descriptive values | In-memory |
| Query draft | Question and selected filters | In-memory |
| Operation result | Mode, status, sanitized diagnostics, actual or sample output | In-memory; cleared on mode change |

Metadata definitions do not grant access. Mode changes do not alter backend permissions. Missing metadata in old input does not imply a synthesized value.

## 10. External dependencies and historical observations

The following were observed in an earlier supplied archive, not verified against today's working tree. Re-inspect before planning. New local code may supersede every item here.

| Area | Earlier observation | Planning consequence |
|---|---|---|
| Ingestion | `POST /api/v1/document-ingestion/jobs`, synchronous multipart upload | Do not assume background jobs or polling. |
| Upload input | `file`, `source_id`, `knowledge_space_id`, `version`, `processing_profile` | Custom metadata support must be verified separately. |
| Upload output | `status`, `source_id`, `version`, `chunks_indexed`, `request_id` | Map existing fields accurately. |
| Upload limits | Default 20 MiB; HTTP accepts PDF/DOCX/TXT/MD | Confirm actual configuration and parser availability. |
| Answer | `POST /api/v1/answers`, question-only input, extra fields forbidden | Full filter submission may be blocked. |
| Answer output | `status`, `answer`, `citations`, `request_id` | Do not assume evidence excerpts/download endpoints. |
| Authentication | Answer dependency returned 401 unconditionally | UI login alone cannot enable Answer API. |
| Workflows | Graph/state files empty; runtime registry without executors | Backend implementation is a separate dependency. |
| CGC | Not present in supplied archive | Inspect local sibling directory; do not guess APIs. |

Public API observations are integration constraints, not a request to change these contracts.

## 11. Definition of done and evidence

### Demo release gate — required

All P1 stories and their applicable acceptance scenarios pass. The UI runs independently, metadata configuration persists, and the three demonstrations work without operational network calls. Type checking/build succeed. The README documents startup, credentials, modes, limitations, and manual verification steps.

### Real integration report — required, completion conditional on dependencies

For each available operation, record the endpoint, tested contract, actual test result, and evidence. Each operation must be classified as one of:

- Connected and tested.
- Implemented adapter, real execution not tested.
- Blocked by an identified external dependency.
- Demo only.

Do not label mocked tests as end-to-end integration tests. A documented backend blocker may coexist with a completed demo release; it must not be presented as completed real integration. Missing UI behavior is not an external blocker.

### Required deliverables

- Runnable `hamtayar-ui` source, lockfile, and environment example without secrets.
- Persian README with PowerShell setup/start commands and configuration guidance.
- Small integration map separating existing APIs, permitted mapping changes, and deferred backend work.
- Test/build results with blocked or unexecuted checks stated explicitly.
- Updated Spec Kit specification, plan, and task status reflecting the delivered scope.

## 12. Risks and bounded responses

| Risk | Response |
|---|---|
| Backend capabilities changed since the archive | Inspect the current tree; do not perpetuate historical assumptions. |
| Demo looks like a completed integration | Persistent mode labels and separate integration status report. |
| Operator assumes metadata was enforced | Intended/transmitted previews and explicit reduced-test choices. |
| UI task grows into domain backend work | Apply FR-037; record separate follow-up work. |
| Hardcoded login is confused with security | Label it as UI-only; preserve backend authorization. |
| Browser settings are lost or corrupted | Explain local scope; provide explicit restore defaults and temporary use. |

## 13. Spec Kit handoff

### 13.1 Governance and feature ownership

Read the existing constitution and applicable AGENTS.md before generating artifacts. Preserve the user's Git workflow and changes. Do not reinitialize Spec Kit, replace the constitution, or create repositories/branches automatically just to match an example.

Select one authoritative Spec Kit feature directory using the installed setup. Record its owner and the sibling UI/backend paths. Avoid competing copies of `spec.md` and `tasks.md` across repositories. If Spec Kit is already managed in the backend repository, that setup can own the feature while the implementation target remains the sibling UI, subject to repository rules.

### 13.2 Input to specify

Use Sections 1–12 as the product source. Generate prioritized user stories, testable functional requirements, edge cases, and measurable success criteria. Preserve requirement IDs or maintain an explicit mapping. Keep historical observations qualified as historical. Do not turn blocked backend capabilities into implementation scope.

Suggested agent input, after invoking the installed `specify` command/skill:

```text
Read Hamtayar_Demo_UI_PRD_EN.md and create the feature specification for
hamtayar-demo-ui from Sections 1–12. Respect the existing constitution and
AGENTS.md. Preserve the lightweight demo scope, fixed UI-only login,
manual browser-local metadata, explicit Demo/API separation, and sibling
hamtayar-ui location. Distinguish demo completion from verified real
integration. Inspect current source before asserting backend readiness.
Do not implement code or expand the task into backend domain development.
```

### 13.3 Clarification focus

Resolve only genuine conflicts or missing decisions discovered in the repository. The demo account, Persian RTL UI, manual metadata, browser-local definitions, default Demo mode, and absence of production authentication are already decided. Do not ask the user to choose them again.

### 13.4 Planning constraints — not additional product scope

- Preferred new-project stack: React, TypeScript, Vite; reuse a suitable existing UI if present.
- Prefer simple pages/components/services/config/types organization and plain CSS or Tailwind.
- Use a central API client, shared metadata field renderer, replaceable `authService`, and `metadataConfigService`.
- Suggested browser persistence: sessionStorage for the demo session; localStorage for field definitions.
- Keep fixtures separate from real HTTP adapters. Use configurable API/proxy addresses and timeouts.
- Existing backend: Python/FastAPI; reuse its public boundaries and existing workflow orchestration. Do not put orchestration into the frontend.
- Do not place service secrets in frontend environment variables or bundles.
- Plan meaningful login, metadata, payload-mapping, Demo/API separation, and integration tests. Add backend regression checks only when backend code changes.

Suggested input to the installed `plan` command/skill:

```text
Plan the approved demo-ui specification using the constraints in PRD
Section 13.4. Inspect current Hamtayar and optional CGC/HamtayarDemo APIs.
Document actual payload mappings and blockers. Keep the UI runnable without
services and avoid new auth services, databases, domain filters, or workflows.
Use the existing constitution. Identify affected paths and verification steps.
```

### 13.5 Tasks, analysis, implementation, and verification

Generate dependency-ordered tasks mapped to stories and requirements: shell/login/modes, metadata settings, document demonstration, Q&A demonstration, codebase demonstration, verified API adapters, and validation/documentation. Every integration task needs a dependency condition and an honest completion criterion.

Run cross-artifact consistency analysis before implementation and resolve scope drift at its source. Execute implementation only after specification and plan review. Validate against the acceptance scenarios and the two delivery gates. If the installed Spec Kit supports a convergence step, use it to identify remaining implementation gaps; do not convert legitimate external blockers into fictitious completions.

Command invocation varies by installed agent integration and version. Use the commands/skills actually available locally rather than assuming slash, dotted, hyphenated, or dollar-prefixed syntax. These workflow steps are agent interactions, not ordinary PowerShell commands.

## 14. Process references

Checked on 2026-11-04. These references explain the workflow; product requirements above derive from the agreed Hamtayar scope.

- [Official Spec Kit quickstart](https://github.github.com/spec-kit/quickstart.html)
- [Official Spec Kit command reference](https://github.github.com/spec-kit/reference/agentic-sdd.html)
- [Official Spec Kit repository](https://github.com/github/spec-kit)
