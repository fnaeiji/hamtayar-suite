---
description: "Dependency-ordered implementation tasks for Hamtayar Demo UI"
---

# Tasks: Hamtayar Demo UI

**Input**: Design documents from `specs/001-hamtayar-demo-ui/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`.

**Testing**: Behavioral test tasks are included because the project constitution requires repeatable user-behavior and integration-boundary tests. Live service checks remain conditional and must not be presented as fixture/mock integration.

**Organization**: Tasks are grouped by the six user stories in the specification. Task IDs show execution order; [P] marks only work that can proceed concurrently without editing the same files or depending on an unfinished task.

## Phase 1: Setup

**Purpose**: Create the new frontend package and reproducible developer tooling.

- [ ] T001 Initialize the React, strict TypeScript, and Vite SPA with React Router, `react-markdown`, Vitest, React Testing Library, ESLint, and Prettier dependencies in `package.json`, `package-lock.json`, `index.html`, `vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`, and `src/main.tsx`.
- [X] T002 Configure Vitest/RTL setup and npm scripts for `dev`, `build`, `preview`, `format`, `format:check`, `lint`, `typecheck`, and `test` in `vitest.config.ts`, `tests/setup.ts`, `eslint.config.mjs`, `.prettierrc.json`, and `package.json`.
- [X] T003 Add generated output, dependency artifacts, and `.env.local` to `.gitignore`; create a non-secret `.env.example` containing service addresses/timeouts and any required verified API upload limit in `.gitignore` and `.env.example`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared data contracts, mode lifecycle, and RTL/accessibility foundations required by all stories.

- [X] T004 [P] Define shared metadata types in `src/types/metadata.ts`: `key` is a unique stable English identifier; `labelFa` is a Persian label; `group` is `document` or `user`; `type` is `text`, `number`, `boolean`, `select`, or `multi_select`; `options` are stable English values with Persian labels for selection fields; `required`, `enabled`, `visibleInForm`, and document-only `filterable` are separate flags.
- [X] T005 [P] Define shared mode, operation status, result provenance, sanitized diagnostic, and per-operation lifecycle types in `src/types/operations.ts`, using `idle`, `validating`, `pending`, `completed`, `failed`, and `uncertain` and preserving the operation's captured `demo`/`api` mode.
- [X] T006 Create the shared typed service configuration and HTTP transport in `src/config/services.ts` and `src/services/api/httpClient.ts`; read and validate non-secret `VITE_HAMTAYAR_BASE_URL`, `VITE_HAMTAYAR_TIMEOUT_MS`, `VITE_HAMTAYAR_MAX_UPLOAD_BYTES` when required, `VITE_CGC_BASE_URL`, and `VITE_CGC_TIMEOUT_MS` values from `.env.local`, apply configured timeouts and abort cleanup, normalize sanitized errors, and include no credentials or provider secrets. Never enable an API upload unless its current per-service size limit is verified.
- [X] T007 Implement the lightweight in-memory operation manager in `src/services/operations/operationManager.ts`; assign each operation an identity/generation, retain mode-tagged state across workspace navigation, ignore stale responses, clean up timers/polling/listeners when no longer needed, clear transient drafts/results and stop local observers on logout, and never claim browser abort cancels service-side work.
- [X] T008 Implement the shared mode provider in `src/app/ModeProvider.tsx`: first launch defaults to Demo; mode switching is disabled while pending; after an allowed switch transient results/history clear while metadata definitions remain.
- [X] T009 [P] Add shared Persian RTL base styles and design tokens, including correct LTR wrappers for technical identifiers/JSON, in `src/styles/tokens.css`, `src/styles/global.css`, and `src/components/common/LtrText.tsx`.
- [X] T010 Create accessible shared empty/loading/status/connection components with visible labels and non-color-only status cues in `src/components/common/StatusMessage.tsx`, `src/components/common/ConnectionBadge.tsx`, and `src/components/common/LoadingState.tsx`.

**Checkpoint**: Shared types, mode lifecycle, and global UI foundations are ready before story work.

---

## Phase 3: User Story 1 - Enter and navigate the demo (Priority: P1)

**Goal**: Sign into the UI-only demo, navigate all workspaces, retain session across tab refresh, and log out without any backend.

**Independent Test**: With services stopped, valid credentials open the dashboard; invalid credentials remain on login; every workspace link opens its route; refresh retains the tab session; logout clears it.

### Validation tasks

- [X] T011 [US1] Write accessible flow tests for valid/invalid login, route guarding, refresh retention, logout clearing temporary results/stopping local observers, navigation retaining a pending operation outcome, stale-response rejection, active mode visibility, and blocking a mode switch while an operation is pending in `tests/flows/auth-navigation.test.tsx`.

### Implementation tasks

- [X] T012 [US1] Implement the fixed UI-only credential check and `sessionStorage` session lifecycle without storing the password in `src/features/auth/authService.ts`.
- [X] T013 [US1] Implement login form, Persian validation errors, protected workspace routes with temporary workspace placeholders, and redirects in `src/features/auth/LoginPage.tsx`, `src/app/ProtectedRoute.tsx`, `src/app/WorkspacePlaceholder.tsx`, and `src/app/router.tsx`.
- [X] T014 [P] [US1] Implement the experimental-environment dashboard shell, Overview cards for all three workspaces, five workspace links, logout control, and visible Demo/API selector in `src/app/DashboardLayout.tsx`, `src/features/overview/OverviewPage.tsx`, and `src/components/common/ModeSelector.tsx`.

**Checkpoint**: US1 works independently with placeholder workspace content and no service dependency.

---

## Phase 4: User Story 2 - Configure local metadata (Priority: P1)

**Goal**: Manage browser-local field definitions that drive document and Q&A forms and survive browser restart when persistence works.

**Independent Test**: Add a filterable document select field, verify it appears in the document form and Q&A filters, refresh/restart, and confirm it persists; validate `0`/`false`, invalid keys/options, destructive-change warnings, and storage failure behavior.

### Validation tasks

- [X] T015 [P] [US2] Write tests for default definitions, unique/reserved keys, type/options validation, required `0`/`false`, hidden/disabled stale values, persistence/reload specifically under localStorage key `hamtayar-demo-ui.metadata.v1`, Restore defaults changing only that key, and storage failure in `tests/features/metadata/metadataConfigService.test.ts`.
- [X] T016 [P] [US2] Write accessible tests for add/edit/delete/restore, destructive-change confirmation, dynamic field rendering, and the warning that definitions are browser-local in `tests/features/metadata/MetadataSettingsPage.test.tsx`.

### Implementation tasks

- [X] T017 [P] [US2] Implement metadata validation, persistence under only localStorage key `hamtayar-demo-ui.metadata.v1`, in-memory fallback, and defaults in `src/services/metadata/metadataConfigService.ts`; reject duplicate/malformed/reserved keys (`tenant_id`, `acl_principals`, `principals`, `access_scope`, `subject_id`) and invalid or duplicate selection options; seed exactly `department` (document/select: engineering, hr, finance), `project` (document/text), `document_type` (document/select: guide, report, policy), `tags` (document/multi_select), `display_name` (user/text), `expertise` (user/text), and `answer_language` (user/select: fa, en), each with Persian labels. Restore defaults MUST change only the named key.
- [X] T018 [P] [US2] Implement reusable metadata field controls in `src/components/metadata/MetadataFieldControl.tsx` and `src/components/metadata/MetadataFields.tsx`; `0` and `false` count as supplied values, required document fields do not become required query filters, and hidden/disabled fields do not submit stale values.
- [X] T019 [US2] Implement metadata settings add/edit/delete/restore flows with local-only notice, invalid-definition messages, and confirmation before discarding entered values in `src/features/metadata/MetadataSettingsPage.tsx` and register its route in `src/app/router.tsx`.

**Checkpoint**: US2 can be tested independently; document and Q&A forms can consume its shared field components.

---

## Phase 5: User Story 3 - Demonstrate document ingestion (Priority: P1)

**Goal**: Select multiple documents, configure independent metadata, preview and run a fully labeled fixture demonstration with independent outcomes.

**Independent Test**: With services stopped, submit multiple files in Demo mode, verify a labeled fixture result for each, confirm no operational network requests, and retain other files' outcomes if one fails.

### Validation tasks

- [ ] T020 [US3] Write document-flow tests for selection/drop using identical file-type/size validation, no artificial Demo-mode size cap, API upload blocked when the per-service limit is unknown, file facts, per-file metadata, shared values with overrides, preview/clear, independent partial outcomes, Demo labeling, and zero operational requests in `tests/features/documents/DocumentIngestionPage.test.tsx`.

### Implementation tasks

- [ ] T021 [US3] Define document draft and per-file operation state in `src/features/documents/documentTypes.ts`; keep file content in memory and model `sourceId`, `knowledgeSpaceId`, `version`, `processingProfile`, `customMetadata`, mode, status, and result independently for each file.
- [ ] T022 [US3] Add representative labeled sample document inputs and outcomes in `src/fixtures/documents.ts`; fixtures must identify themselves as simulated and must not call the HTTP client.
- [ ] T023 [US3] Implement document selection/drop through one shared file-type/size validator, per-file name/type/size, editable fixed fields, metadata controls, and shared values with per-file overrides in `src/features/documents/DocumentIngestionPage.tsx` and `src/features/documents/DocumentFileCard.tsx`; use no artificial Demo size cap, block API upload when its verified service limit is unknown, suggest an editable UUID source ID, and retain that ID for deliberate retry.
- [ ] T024 [US3] Implement request preview, required-value/confirmed-limit validation, clear behavior, independent Demo outcomes, and a conspicuous simulated/no-backend label in `src/features/documents/documentsService.ts` and `src/features/documents/DocumentIngestionPage.tsx`; replace the document workspace placeholder route in `src/app/router.tsx`.

**Checkpoint**: US3 produces a complete useful local demonstration with every service stopped.

---

## Phase 6: User Story 4 - Demonstrate Q&A (Priority: P1)

**Goal**: Enter a question, descriptive user values, and document filters; inspect a labeled sample answer without claiming real personalization/filtering.

**Independent Test**: With services stopped, submit a question plus user values and filters in Demo mode; verify the query preview, sample answer/sources, no network calls, preserved input on errors, and safe rendering of untrusted Markdown.

### Validation tasks

- [ ] T025 [US4] Write Q&A tests for filter equality/any-of/AND, omission of unset values, preservation of `0`/`false`, explicit question-only disclosure, retained input on errors, and safe Markdown with script/unsafe-URL examples in `tests/features/qa/QAPage.test.tsx` and `tests/components/SafeAnswerMarkdown.test.tsx`.

### Implementation tasks

- [ ] T026 [P] [US4] Implement the internal query model and filter conversion in `src/features/qa/queryModel.ts`: one value means equality, multiple selected values mean any-of, fields combine with AND, unset values are omitted, and `0`/`false` remain values; do not emit arbitrary database syntax.
- [ ] T027 [P] [US4] Add labeled sample answers and citations as local fixtures in `src/fixtures/answers.ts`; never present them as API output or as evidence retrieved for the user's metadata/filters.
- [ ] T028 [P] [US4] Implement answer Markdown rendering in `src/components/answers/SafeAnswerMarkdown.tsx` using `react-markdown` safe defaults; do not enable raw HTML, unsafe plugins, `dangerouslySetInnerHTML`, or a custom unsafe URL transform.
- [ ] T029 [US4] Implement the Q&A form, requiring a non-empty trimmed question and enforcing the current API's 1–4096 character limit for API requests, dynamic descriptive-user fields, derived filter controls, question-only preview, Demo result/sources, and clear separation from API claims in `src/features/qa/QAPage.tsx` and `src/features/qa/qaService.ts`; replace the Q&A workspace placeholder route in `src/app/router.tsx`.

**Checkpoint**: US4 runs entirely on fixtures and cannot be mistaken for personalized or filtered backend output.

---

## Phase 7: User Story 5 - Demonstrate codebase processing (Priority: P1)

**Goal**: Demonstrate archive selection and sample processing status/logs while keeping the workspace usable if CGC is missing.

**Independent Test**: With CGC/HamtayarDemo stopped, select an archive, enter a project name, run the Demo fixture flow, and verify simulated status/log labels and continued access to other workspaces.

### Validation tasks

- [ ] T030 [US5] Write codebase-flow tests for archive selection, project name, labeled sample states/logs, no operational requests in Demo, API-unavailable messaging, and unaffected navigation in `tests/features/codebase/CodebasePage.test.tsx`.

### Implementation tasks

- [ ] T031 [US5] Add clearly labeled codebase sample status transitions and logs in `src/fixtures/codebase.ts`; do not describe fixture transitions as observed API workflow nodes or progress.
- [ ] T032 [US5] Implement the archive/project form, fixture demonstration, explicit unavailable state in API mode, and workspace-isolated errors in `src/features/codebase/CodebasePage.tsx` and `src/features/codebase/codebaseService.ts`; replace the Codebase workspace placeholder route in `src/app/router.tsx`.

**Checkpoint**: US5 remains demonstrable without CGC and its unavailability does not affect other routes.

---

## Phase 8: User Story 6 - Test available services (Priority: P2, conditional)

**Goal**: Exercise only contract-verified service operations in API mode and show actual results or precise blockers. P2 work never blocks P1 Demo completion.

**Independent Test**: For each service that passes its readiness gate, inspect actual transmitted fields and responses; verify failures stay failures, unsupported payloads are blocked, secrets are absent, and the UI never falls back to fixtures.

### Validation tasks

- [ ] T033 [P] [US6] Write mocked Hamtayar adapter and diagnostics tests in `tests/services/hamtayarAdapter.test.ts` and `tests/components/TestDetailsPanel.test.tsx`; verify ingestion uses exactly `file`, `source_id`, `knowledge_space_id`, `version`, `processing_profile`, maps `status`/`source_id`/`version`/nullable `chunks_indexed`/optional `request_id`, renders null chunk count as “گزارش نشده”, sends Q&A as `{question}` only, distinguishes 401/422/413/500/503/504/network timeout, and never renders secrets, stack traces, or fabricated IDs.
- [ ] T034 [P] [US6] Write CGC readiness/security tests in `tests/services/cgcAdapter.test.ts` proving missing verification/configuration returns a blocked outcome and the adapter rejects a non-local target for the unauthenticated service.

### Implementation tasks

- [ ] T035 [US6] Inspect the intended running service settings and record per-operation URL, CORS/proxy, executor/auth readiness, limits, and evidence as `Connected and tested`, `Adapter only`, `Blocked`, or `Demo only` in `docs/integration-map.md`; retain disabled API controls for any gate that fails.
- [ ] T036 [P] [US6] Implement Hamtayar clients and runtime response validation in `src/services/api/adapters/hamtayarAdapter.ts` using only observed contracts and explicit UI-model-to-wire-DTO mapping: ingestion is synchronous and per-file; custom metadata requires explicit reduced-test confirmation; Q&A wire input is `{question}` only (1–4096 characters), with current 401/503 responses treated as blockers and no auth bypass or fixture fallback.
- [ ] T037 [P] [US6] Verify current CGC OpenAPI/capability/diagnostic output, endpoint sequence, configured archive limits, status/log/cancellation semantics, CGC executable, both Neo4j targets, CORS/proxy, and local-only reachability; update `specs/001-hamtayar-demo-ui/contracts/cgc-local-api.md` with observed evidence and keep API actions disabled if any prerequisite fails.
- [ ] T038 [US6] Implement `src/services/api/adapters/cgcAdapter.ts` only for verified operations and explicitly configured loopback/local targets, with runtime response validation and explicit UI-model-to-wire-DTO mapping; if readiness gates fail, return an actionable blocked result and keep controls disabled without changing the CGC service or exposing it to a network.
- [ ] T039 [P] [US6] Implement the collapsible sanitized request/response/elapsed-time/request-ID panel in `src/components/operations/TestDetailsPanel.tsx`; show intended and actual transmitted payloads separately, omit secrets/stack traces, and never fabricate request IDs or response data.
- [ ] T040 [US6] Connect API mode to per-operation readiness and verified adapters in `src/services/operations/operationService.ts` and the document/Q&A/codebase pages; prevent duplicate submits/mode changes while pending, preserve uncertain upload outcomes/source IDs, distinguish `no_evidence` from provider failure, and never transition an API failure into fixture output.

**Checkpoint**: Any unavailable operation has an explicit blocker; each enabled operation reports actual response data only. Demo mode remains independent.

---

## Phase 9: Polish and Cross-Cutting Concerns

**Purpose**: Complete user-facing guidance, visual/accessibility checks, and verifiable delivery evidence.

- [ ] T041 [P] Write the Persian README with PowerShell setup/start commands, fixed demo credentials, modes, local configuration, limitations, and manual verification steps in `README.md`.
- [ ] T042 [P] Document existing APIs, permitted client mappings, integration results/blockers, and deferred backend work in `docs/integration-map.md`, ensuring each operation uses one of the four classifications in the spec.
- [ ] T043 Review and correct RTL/LTR layout, keyboard navigation, visible focus, labels, non-color status cues, 1366×768 page overflow, and 390px action availability in `src/styles/global.css` and affected `src/features/*` components.
- [ ] T044 Run the documented quickstart scenarios and repeatable `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run build`; record actual outcomes, environment, and blocked API checks in `README.md` without claiming unrun checks passed.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: T001 first; T002 and T003 follow the package scaffold and can proceed in parallel.
- **Foundational (Phase 2)**: Depends on setup. T004, T005, and T009 can proceed in parallel; T008 depends on T005; T010 depends on T009. All foundational tasks block story implementation.
- **US1 (Phase 3)**: Depends on foundation; establishes navigable route shell.
- **US2 (Phase 4)**: Depends on US1 route shell and shared metadata types; supplies reusable field controls for US3 and US4.
- **US3 (Phase 5)**: Depends on US1 and US2 metadata controls.
- **US4 (Phase 6)**: Depends on US1 and US2 metadata controls; safe answer renderer is local to Q&A.
- **US5 (Phase 7)**: Depends on the US1 route shell. Its page tests and fixtures can be prepared in parallel with US2/US3/US4, but route registration in `src/app/router.tsx` is sequenced after those route changes.
- **US6 (Phase 8)**: Depends on the P1 workspace screens, shared configuration/client in T006, and the in-memory operation manager in T007. Hamtayar adapter work can proceed without CGC; CGC adapter work depends on T037 readiness evidence. Failed gates complete as an explicit blocked/unavailable state, not a fabricated integration.
- **Polish (Phase 9)**: Depends on all selected P1 stories; integration reporting depends on US6 readiness results.

### User story completion order

1. US1 provides the navigation/login walking skeleton.
2. US2 provides shared dynamic fields required by the ingestion and Q&A stories.
3. US3, US4, and US5 complete the three independently labeled P1 demonstrations; US5 can proceed in parallel after the US1 shell.
4. US6 adds only verified P2 adapters and can finish with documented blockers where external dependencies are unavailable.

### Parallel opportunities by story

- **US1**: After T011 passes, T012 auth-service work and T014 dashboard shell can proceed in parallel; T013 route/login wiring consumes the auth behavior and route contract.
- **US2**: T015 validator/storage tests and T016 settings interaction tests are separate files and can proceed together; after they pass, T017 service and T018 renderer use separate files and can proceed together.
- **US3**: No [P]-marked tasks: establish the per-file draft contract in T021 before fixtures and form integration so fixtures/pages share one shape.
- **US4**: After T025 passes, T026 query model, T027 fixture data, and T028 safe renderer use separate files and can proceed in parallel; T029 integrates them into the page.
- **US5**: No [P]-marked tasks: T031 fixture shape should be settled before T032 page/service integration, with the route registered after other route edits.
- **US6**: T033 Hamtayar tests and T034 CGC gate tests can run in parallel; after they pass, T036 Hamtayar adapter, T037 CGC readiness verification, and T039 diagnostics panel can proceed in parallel; T038 waits for T037 and T040 waits for all adapter/UI work.

### Parallel example: US5 after the US1 shell

```text
Task T030: Add Codebase page behavior tests in tests/features/codebase/CodebasePage.test.tsx
Task T031: Add labeled codebase fixtures in src/fixtures/codebase.ts
Task T032: Integrate src/features/codebase/CodebasePage.tsx after fixture shape is agreed
```

## Implementation Strategy

### Walking skeleton

Complete Setup, Foundational, and US1 to demonstrate login and navigation independently. This is a development checkpoint, not the full product Demo release gate.

### P1 Demo MVP

Complete US1–US5. Validate all three workspaces with services stopped and confirm Demo sends zero operational requests. This is the standalone Demo delivery described by the PRD.

### Conditional P2 integration

Complete US6 per operation only after its contract/readiness gates pass. If a gate fails, keep the action unavailable, record the external dependency and evidence, and deliver the P1 Demo without claiming real integration.

## Notes

- Every task uses the required checkbox, sequential ID, optional parallel/story labels, and at least one exact file path.
- Metadata types/validators must preserve the exact constraints described in `data-model.md`; API adapters must follow the contracts under `contracts/`.
- Write each validation task before the corresponding implementation task and confirm its expected failing behavior before implementation.
- No backend service, auth, database, workflow, or CGC changes are in scope.
- Do not claim real-service verification unless the operation was actually exercised and evidence was recorded.
