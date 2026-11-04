# Feature Specification: Hamtayar Demo UI

**Feature Branch**: `001-hamtayar-demo-ui`

**Created**: 2026-11-04

**Status**: Draft

**Input**: User description: "Read `prd/Hamtayar_Demo_UI_PRD_EN.md` and specify it."

## Clarifications

### Session 2026-11-04

- Q1 (service configuration): Service addresses and timeouts are configured locally, not through a user-facing settings screen. The implementation-specific source and typed configuration boundary are recorded in [research decisions](research.md#clarifications-q1q4).
- Q2 (operation lifecycle): An operation remains observable when the operator navigates between workspaces; logout clears temporary UI state and stops local observation, without claiming to cancel server work. Its implementation boundary is recorded in [research decisions](research.md#clarifications-q1q4).
- Q3 (metadata persistence): Metadata definitions persist in the current browser. Restore defaults changes only the UI-owned metadata setting and leaves unrelated browser data unchanged. The chosen storage key is recorded in [research decisions](research.md#clarifications-q1q4).
- Q4 (file validation): Picker and drag-and-drop apply the same file type and size rules. Demo has no artificial size cap; API uploads remain blocked until the applicable service limit is verified. The shared-validator implementation decision is recorded in [research decisions](research.md#clarifications-q1q4).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enter and navigate the demo (Priority: P1)

A presenter signs in with the fixed demo account, moves among Overview, Codebase, Document Ingestion, Q&A, and Metadata Settings, refreshes the page, and signs out. The dashboard remains usable without a backend.

**Why this priority**: This is the entry point and navigation shell needed to demonstrate every workspace.

**Independent Test**: With all services stopped, sign in with the specified demo credentials, visit every workspace, refresh, and log out. Invalid credentials must not open the dashboard.

**Acceptance Scenarios**:

1. **Given** the login page, **When** the user enters `demo` / `Hamtayar123!`, **Then** the dashboard opens and identifies itself as an experimental environment.
2. **Given** the login page, **When** either credential is incorrect, **Then** the user remains on the login page and sees a clear Persian error.
3. **Given** a signed-in tab, **When** it is refreshed, **Then** the UI session remains; **When** the user logs out, **Then** the session is removed and login is shown.
4. **Given** any workspace, **When** the user views navigation or operation results, **Then** the active mode is clear and status is not represented by color alone.

### User Story 2 - Configure local metadata (Priority: P1)

An operator adds, edits, disables, deletes, or restores field definitions and uses them in document and Q&A forms. Definitions belong to the current browser and do not grant identity or access.

**Why this priority**: Configurable fields are central to preparing realistic demonstrations without a server-side registry.

**Independent Test**: Add a filterable document select field, use it in document and query forms, refresh or restart the browser, then verify the definition remains and the selected query control is available.

**Acceptance Scenarios**:

1. **Given** default metadata settings, **When** the operator adds a valid field, **Then** the relevant form updates without a code change.
2. **Given** a document field marked filterable, **When** Q&A is opened, **Then** a corresponding filter control is available; required document fields do not automatically become required query filters.
3. **Given** a required numeric or boolean field, **When** its value is `0` or `false`, **Then** it is treated as supplied; missing required values, duplicate/reserved keys, invalid types, and invalid options are rejected.
4. **Given** a field definition whose change would discard entered values, **When** the operator changes or deletes it, **Then** the UI warns and hidden or disabled stale values are not submitted.
5. **Given** browser persistence is unavailable, **When** a definition is saved, **Then** the UI warns that it is temporary and continues with in-memory settings.

### User Story 3 - Demonstrate document ingestion (Priority: P1)

An operator selects one or more documents, assigns fixed ingestion fields and custom metadata per file, previews the request, and submits a labeled local demonstration. Each file has its own outcome.

**Why this priority**: Document ingestion is a primary product capability and must be demonstrable independently of service availability.

**Independent Test**: In Demo mode with services stopped, select multiple files, set different metadata, preview and submit, and verify clearly labeled sample outcomes with no operational network calls.

**Acceptance Scenarios**:

1. **Given** a document ingestion form, **When** one or more files are selected or dropped, **Then** each file shows its name, type, size, source identity, and editable request values.
2. **Given** multiple files with different metadata, **When** Demo or API submissions complete, **Then** each file's request and outcome is independent and a failure does not erase another file's success.
3. **Given** Demo mode, **When** the operator submits, **Then** local fixtures produce a simulated outcome labeled “نمایشی؛ داده‌ای در بک‌اند ثبت نمی‌شود” and no operational request is sent.
4. **Given** API mode where custom metadata is unsupported, **When** metadata has been entered, **Then** submission is blocked unless the operator explicitly chooses the reduced upload test; intended and transmitted data are shown separately.
5. **Given** an ingestion timeout or connection loss, **When** the UI reports the outcome, **Then** it describes the server result as uncertain, does not automatically retry, and retains the source identity for a deliberate retry.
6. **Given** a file is selected through the picker or dropped, **When** file validation runs, **Then** both paths apply the same file-type/size rules; Demo mode has no artificial size cap, while API submission is blocked until the service's limit is verified.

### User Story 4 - Demonstrate Q&A (Priority: P1)

An operator enters a question, descriptive user values, and document filters, then inspects a labeled sample answer and sources. Demo output is not represented as personalized or retrieval-filtered backend output.

**Why this priority**: Q&A is a primary workspace and must remain usable even when answer services or authorization are unavailable.

**Independent Test**: With services stopped, enter a question, user values, and filters, submit in Demo mode, and verify a labeled answer, sample sources, and no operational request.

**Acceptance Scenarios**:

1. **Given** a question and configured metadata, **When** the operator previews the request, **Then** the preview distinguishes question, descriptive user metadata, and filters.
2. **Given** query filters, **When** a single value or multiple selected values are submitted, **Then** the filter represents equality or any-of respectively, different fields combine with AND, and unset fields are omitted while `0` and `false` remain supplied.
3. **Given** API mode that cannot accept user metadata or filters, **When** the operator submits the full input, **Then** the request is blocked; only the explicit “تست فقط پرسش” action may send a question-only request and its result is not described as personalized or filtered.
4. **Given** invalid input or API failure, **When** submission ends, **Then** entered input is preserved and the user receives an actionable Persian message.
5. **Given** an answer result, **When** displayed, **Then** actual statuses, citations, and identifiers are used; `no_evidence` differs from provider failure, Markdown is safe, and no unsupported memory or streaming is implied.

### User Story 5 - Demonstrate codebase processing (Priority: P1)

A presenter selects a code archive, enters a project name, and walks through explicitly simulated processing states and logs in Demo mode. If an actual service is unavailable, the UI explains that limitation without disabling other workspaces.

**Why this priority**: Codebase is one of the three promised demonstration areas; its Demo must not depend on an unavailable sibling service.

**Independent Test**: With the code processing service absent, open Codebase, run its fixture demonstration, and verify that simulated states and logs are labeled while Document Ingestion and Q&A remain usable.

**Acceptance Scenarios**:

1. **Given** Demo mode, **When** the operator selects an archive and starts the demonstration, **Then** the UI shows a complete labeled fixture flow with sample status and logs.
2. **Given** API mode, **When** no verified code processing service is available, **Then** upload and processing actions remain unavailable with an explanation and no guessed routes are called.
3. **Given** the code processing service is unavailable, **When** another workspace is opened, **Then** it remains usable.

### User Story 6 - Test available services (Priority: P2)

A developer or tester uses API mode to exercise only verified, available service operations, inspect sanitized requests and actual responses, and distinguish success from blockers. This story is conditional on existing service contracts and dependencies.

**Why this priority**: Real integration is useful after the standalone demo is complete, but external readiness must not block the P1 demo or be fabricated.

**Independent Test**: For each available operation, compare the displayed transmitted request and result with the actual service response; when a dependency is absent, verify a precise blocker and no fixture fallback.

**Acceptance Scenarios**:

1. **Given** API mode and a verified available operation, **When** a request succeeds, **Then** the UI reports success only from the actual response and shows only returned fields.
2. **Given** API mode and an unavailable or unauthorized operation, **When** the user submits, **Then** the UI reports the blocker and never falls back silently to fixtures or bypasses service authorization.
3. **Given** an operation in progress, **When** the user attempts a second submission or mode switch, **Then** duplicate submission and mode mixing are prevented.
4. **Given** operation details, **When** the user expands Test details, **Then** sanitized intended and transmitted payloads, response, elapsed time, and supplied request identifier are available; no identifier is invented.
5. **Given** an operation is pending, **When** the user navigates to another workspace and returns, **Then** its mode-tagged outcome remains available; **When** the user logs out, **Then** temporary UI data and local observation are cleared without claiming service-side work was canceled.

### Edge Cases

- Browser storage is unavailable, corrupt, or contains invalid metadata definitions; usable in-memory defaults remain available and the persistence limitation is disclosed.
- A metadata key is duplicated, reserved, malformed, or has missing/invalid options; the definition is rejected without changing existing definitions.
- A user changes or disables a field after entering a value; stale values cannot silently enter a later request.
- A selected file exceeds a confirmed limit or uses a format whose parser support is unconfirmed; the UI explains the known limitation without claiming parser readiness from an HTTP allowlist.
- An API upload limit has not been verified for the configured service; the UI blocks submission and explains the missing limit instead of applying a guessed cap.
- A multi-file request partially succeeds, one file fails, or a connection is lost after upload; independent outcomes and uncertain server completion are preserved.
- The backend omits a nullable count or request identifier; the UI reports “گزارش نشده” for a missing chunk count and does not fabricate an identifier.
- A response has `no_evidence`, malformed data, unsafe Markdown, or sensitive diagnostic content; the UI distinguishes the result, handles invalid data safely, and excludes secrets and stack traces.
- A health check succeeds while the relevant operation is unauthorized or has no executor; reachability is not presented as operational readiness.
- A mode switch is requested while work is pending; it is prevented. After switching, transient results and mode-specific histories are cleared, while metadata definitions remain.
- A descriptive user field resembles an identity or access claim; it is treated only as supplied test input and never as verified identity or authorization.

## Requirements *(mandatory)*

### Functional Requirements

#### Entry, navigation, and modes

- **FR-001**: The UI MUST accept only the fixed demo credentials `demo` / `Hamtayar123!`; invalid credentials MUST leave the user at login with a clear Persian error.
- **FR-002**: The UI MUST retain signed-in state for the current browser tab session, remove it at logout, and never persist the password.
- **FR-003**: Dashboard routes MUST require the demo UI session and identify login/dashboard as an experimental environment; this gate MUST NOT be represented as security enforcement.
- **FR-004**: Navigation MUST provide Overview, Codebase, Document Ingestion, Q&A, Metadata Settings, and Logout. Overview MUST show the three workspaces and accurate connection information.
- **FR-005**: Workspaces MUST provide appropriate empty, loading, success, and failure states and MUST NOT fabricate operational counts or success rates.
- **FR-006**: The UI MUST expose explicit Demo and API modes, default a first launch to Demo, and show the active mode on every operation and result.
- **FR-007**: Demo mode MUST use local fixtures, send no operational requests to services or model providers, and display “نمایشی؛ داده‌ای در بک‌اند ثبت نمی‌شود”.
- **FR-008**: API mode MUST report success only from actual service responses and MUST NOT silently fall back to fixtures after a failure.
- **FR-009**: Mode switching MUST be prevented during a pending operation; after a switch, transient results and mode-specific histories MUST be cleared while metadata definitions remain.
- **FR-010**: Service reachability MUST be shown separately from the availability of ingestion, answer, or other operations.

#### Local metadata configuration

- **FR-011**: The UI MUST maintain document and descriptive-user field definitions locally and derive query-filter controls from document fields marked filterable.
- **FR-012**: Each definition MUST support a unique English key, Persian label, document/user group, type, applicable options, required/enabled flags, form visibility, and document filterability.
- **FR-013**: The UI MUST support `text`, `number`, `boolean`, `select`, and `multi_select`, validate type, required values, and option membership, and treat numeric zero and boolean false as supplied values.
- **FR-014**: The operator MUST be able to add, edit, delete, and restore defaults. Destructive changes MUST warn about discarded values; duplicate keys and invalid option definitions MUST be rejected.
- **FR-015**: Definitions MUST persist in the current browser across refresh and restart when browser persistence is available. Restore defaults MUST change only the UI-owned metadata setting and MUST NOT alter unrelated browser data. Their local-only nature MUST be explained. If persistence fails, the UI MUST warn and allow temporary use without claiming settings were saved.
- **FR-016**: Forms MUST reflect metadata definitions without a code change. Required document fields MUST NOT automatically become required query filters. Disabled or hidden fields MUST NOT silently contribute stale values to submissions.
- **FR-017**: Definitions MUST reject reserved security/system keys, including `tenant_id`, `acl_principals`, `principals`, `access_scope`, and `subject_id`. Fixed endpoint fields MUST remain distinct from custom metadata.
- **FR-018**: Initial definitions MUST include `department` (document select: engineering/hr/finance), `project` (document text), `document_type` (document select: guide/report/policy), `tags` (document multi-select), `display_name` (user text), `expertise` (user text), and `answer_language` (user select: fa/en), with Persian display labels and stable English option values.

#### Document ingestion

- **FR-019**: The UI MUST support drag-and-drop and selection of multiple documents, show each file's name/type/size, submit each file separately, and retain independent outcomes when another file fails.
- **FR-020**: Each file MUST support editable `source_id` (with a suggested UUID), `knowledge_space_id`, `version`, `processing_profile`, and independent custom metadata; shared values with per-file overrides MUST be supported.
- **FR-021**: The UI MUST provide request preview, submit, and clear actions; picker and drag/drop MUST apply consistent file-type and size rules. Demo mode MUST NOT impose an artificial file-size cap. API submissions MUST use the verified per-service size limit and MUST be blocked when that limit is unknown; the UI MUST NOT infer parser readiness from a supported-format list alone.
- **FR-022**: When an API cannot accept custom metadata, the UI MUST distinguish intended from transmitted data and require an explicit upload-without-custom-metadata choice before omitting entered metadata; otherwise real submission MUST be blocked with an explanation.
- **FR-023**: API mode MUST display only observable real states and fields and MUST NOT invent workflow nodes, progress percentages, jobs, or polling operations. A missing or null chunk count MUST display “گزارش نشده”, not zero.
- **FR-024**: The UI MUST prevent duplicate submissions and automatic ingestion retries. Timeout or connection loss MUST be described as an uncertain server outcome, not guaranteed cancellation; the file's source identity MUST be retained for deliberate retry.

#### Q&A

- **FR-025**: The Q&A workspace MUST provide question input, descriptive-user fields, document filters, submission, an answer area, and sources. Input MUST remain after validation or API failure.
- **FR-026**: Filters MUST support equality for one value, any-of for multiple values, and AND across different fields. Unset filters MUST be omitted; zero and false MUST remain values; arbitrary database query syntax MUST be rejected.
- **FR-027**: The request preview MUST expose an internal model with `question`, `user_metadata`, and `filters`, without implying these names or fields are accepted by an API.
- **FR-028**: If user metadata or filters cannot be accepted/applied, the UI MUST disclose this before submission. Only an explicit “تست فقط پرسش” action MAY send a question without them, and its answer MUST NOT be described as personalized or filtered by omitted values.
- **FR-029**: The UI MUST display actual answer statuses, citations, and request identifiers, distinguish `no_evidence` from provider failure, and MUST NOT invent evidence, links, or citations.
- **FR-030**: Answer Markdown MUST render safely. History MUST remain in memory for the UI session only; unsupported multi-turn backend memory or streaming MUST NOT be implied.

#### Codebase and integration boundaries

- **FR-031**: Codebase MUST provide archive selection, project name, upload and supported processing actions, status, and logs; when a service is unavailable, a complete labeled fixture demonstration MUST remain available.
- **FR-032**: API actions for codebase processing MUST remain disabled until the actual CGC/HamtayarDemo service and its supported operations, formats, limits, identifiers, and status/log meanings are inspected and confirmed.
- **FR-033**: A missing or unavailable codebase service MUST produce a clear unavailable state without disabling Document Ingestion or Q&A; the UI MUST NOT invent routes or create a replacement service.
- **FR-034**: A collapsible Test details panel MUST show sanitized intended/transmitted payloads, responses, elapsed time, and `request_id` when supplied. It MUST NOT invent a server identifier for fixtures or network failures.
- **FR-035**: The UI MUST provide actionable Persian messages for authorization, validation, limits, unsupported formats, rate limits, unavailable services, provider failures, timeouts, and network errors without exposing stack traces, passwords, tokens, or provider secrets.
- **FR-036**: Service addresses and timeouts MUST be configurable as non-secret local settings and MUST NOT be embedded in page content. If trusted service authentication is unavailable, the operation MUST remain blocked; demo login MUST NOT bypass service authorization.
- **FR-037**: Integration MUST use existing ready contracts. Only small compatible transport mapping to an already implemented capability is in scope; domain chunks, storage payloads, retrieval filtering, and unfinished workflows are deferred and documented.
- **FR-038**: The UI MUST NOT silently discard metadata, accept and ignore fields, or append filters to a question as if they were enforced retrieval conditions.
- **FR-039**: Pending operations and their mode-tagged outcomes MUST remain available across workspace navigation, and stale screen updates MUST be ignored. Logout MUST clear temporary drafts/results and stop local observation. Stopping browser-side waiting MUST NOT be described as canceling service-side processing. This feature MUST NOT add a new background service, persistent job system, or backend changes.

### Key Entities

- **Demo session**: Frontend-only signed-in state for the current tab; conveys no backend authority.
- **Metadata field definition**: Local field key, label, group, type, options, validation and visibility settings; persisted in the current browser.
- **Document draft**: Selected file reference, fixed ingestion values, and custom metadata; held in memory until cleared or refreshed.
- **Descriptive user values**: Manually entered test values; held in memory and not verified identity or authorization.
- **Query draft**: Question, descriptive user values, and selected filters; held in memory.
- **Operation result**: Mode, observable status/output, sanitized diagnostics, and actual or sample provenance; held in memory and cleared on mode change.

### Success Criteria *(mandatory)*

#### Measurable Outcomes

- **SC-001**: A presenter can sign in, visit all three workspaces, refresh the tab, and sign out without a backend; all actions produce the expected visible state.
- **SC-002**: In Demo mode, all three workspaces produce labeled sample outcomes and send zero operational requests to Hamtayar, CGC, databases, or model providers.
- **SC-003**: An operator can add a filterable metadata field and see it in the relevant forms within one second on the documented test machine; it remains after browser restart when browser persistence is available.
- **SC-004**: At least 90% of representative users can complete the primary Demo journey—sign in, run one demonstration in each workspace, and identify which results are simulated—without assistance in a moderated acceptance session.
- **SC-005**: At 1366×768, the main demonstration has no page-level horizontal scrolling; at 390px width, navigation and primary actions remain accessible.
- **SC-006**: When API operations are exercised, 100% of reported success states correspond to actual successful responses; unavailable, unauthorized, uncertain, and fixture outcomes are visibly distinguishable.
- **SC-007**: The UI exposes no password, token, provider secret, raw stack trace, fabricated request identifier, citation, operational count, or success rate in user-visible diagnostics or results.

## Assumptions

- The product and user-facing labels are Persian and RTL, while the specification is maintained in English; identifiers, code, paths, and JSON remain legible LTR.
- The fixed demo account is presentation-only and intentionally provides no production identity, permissions, or backend authentication.
- Demo mode is the first-launch default and all P1 workspaces remain useful without external services.
- Metadata settings persist only in the current browser; drafts, document contents, query history, credentials, and sensitive inputs are not persisted by default.
- Real service contracts and readiness must be inspected in the current repository during planning; observations in the PRD's historical archive are not treated as current facts.
- This feature is owned by the sibling `hamtayar-ui` project. Backend changes are limited to small transport mappings for existing capabilities; new domain behavior and services are out of scope.
- P1 Demo completion and P2 real integration are separate outcomes. An external blocker may defer integration without preventing a completed Demo, and must be reported honestly.
- The product requirement for type checking/build success and a Persian README belongs to delivery verification; this specification does not claim those outcomes have already been achieved.

## Dependencies

- Availability and verified contracts of existing Hamtayar operations determine which API mode actions can be enabled.
- Availability and verified contracts of the sibling CGC/HamtayarDemo service determine whether Codebase API actions can be enabled.
- Browser storage availability determines whether metadata definitions survive browser restart; temporary in-memory use remains available if persistence fails.
- The project constitution governs implementation boundaries, including frontend-only ownership and honest separation of Demo results from real integrations.

## Out of Scope

- Production authentication, Padeen, identity verification, roles, user administration, or server-issued demo tokens.
- A server-side metadata registry, settings database, or database migration.
- New ingestion/retrieval workflows, embedding or chunking work, domain retrieval filters, replacement pipelines, or a general code processing gateway.
- Full document management, persistent chat, real-time streaming, or production deployment.
- Automatic commits, pushes, repository moves, constitution replacement, or backend domain changes.

## Approved presentation revision — 2026-11-04

The user's later request supersedes the earlier visible metadata/settings/codebase
Demo requirements for this iteration:

- Match the existing dark navy/blue CGC/HamtayarDemo UI and sidebar/card layout.
- Replace the code workspace name with «همتایار کد». Navigation and its overview
  action open the existing local CGC/HamtayarDemo frontend in the same tab.
  The `/codebase` route provides launch instructions. No API embedding or automatic
  process startup is implied. Main UI dev port is 5174; existing code UI stays 5173.
- Documents and question filters show exactly `center` (Persian label «مرکز», free
  text pending actual organizational choices) and `document_type`.
- The question form has a separate descriptive `person_access_level` field. It is
  not trusted identity, access scope or an enforced permission.
- Hide metadata settings navigation; redirect its previous route to Overview.
  Retain old browser settings without consuming them in this fixed presentation profile.
- Previous dynamic settings components/tests remain reusable but are not routed.
  Previous codebase fixture modules are not used by the active code workspace.

## Approved document/classification revision — 2026-11-04

This later user request supersedes shared metadata controls and the previous prompt
profile: remove the common document fieldset entirely, leaving center and document
type once per file. Both document fields are required for successful Demo submission.
Document types and prompt access levels share stable values normal/confidential/
highly_confidential, labeled عادی / محرمانه / خیلی محرمانه.

The prompt contains exactly two metadata comboboxes: center and access level.
Center options come only from successfully completed Demo documents in this session;
trim/collapse whitespace and deduplicate, exclude failed/pending/unsubmitted drafts.
Keep centers across navigation and clearing draft cards; reset on logout, mode change
or reload with other session-only demo data. Do not infer a backend registration.
Access level maps to document_type equality in the intended UI query; do not infer
permission hierarchy, trust user-entered scope or claim real filtered retrieval.
The document_type filter control is not separately rendered in the prompt.

## Approved typography and identity revision — 2026-11-04

The later user request replaces exact visual matching with a formal, independent
main Hamtayar identity that remains compatible with the code workspace: light cool
canvas, white surfaces, navy sidebar/hero, restrained blue accents and readable
Persian typography. Bundle Vazirmatn 400/500/600/700 locally via Fontsource rather
than relying on a font name or remote font stylesheet.

The user also explicitly authorizes a narrowly scoped frontend branding edit to
CGC/HamtayarDemo: its visible brand, browser title and footer must say همتایار کد.
No CGC workflow, backend, credentials or endpoint behavior changes are included.
