# Research: Hamtayar Demo UI

## Clarifications Q1–Q4

These decisions resolve the specification's open product questions. User-visible behavior is stated in `spec.md`; implementation choices remain here and in `plan.md`.

- **Q1 — Local service configuration**: Read non-secret service addresses and timeouts from `.env.local` through one shared typed configuration module. Do not add a user-facing settings screen for these values.
- **Q2 — Operation lifecycle across navigation**: Keep pending operations and mode-tagged outcomes in a lightweight in-memory frontend manager so workspace navigation does not discard them. Logout clears temporary state and stops local observation. Do not add a background service, persistent job system, or backend changes; browser-side abort does not imply server-side cancellation.
- **Q3 — Metadata storage ownership**: Store definitions under exactly `hamtayar-demo-ui.metadata.v1`; Restore defaults may modify only this UI-owned localStorage key.
- **Q4 — Document file validation**: Use one shared file type/size validator for picker and drag/drop. Do not impose an artificial Demo size cap. Block API uploads until the applicable service's upload limit is verified.

**Date**: 2026-11-04
**Scope**: Resolve implementation choices and inspect currently available service contracts for `hamtayar-demo-ui`.

## Findings and decisions

### 1. Application foundation

- **Decision**: Start a single React + strict TypeScript + Vite browser application in the current repository. Use Node.js 24 LTS and npm with one committed lockfile.
- **Rationale**: The project constitution requires React, TypeScript, and Vite for a new UI. The repository currently has no source, package manifest, lockfile, README, or test harness. Node.js 24 is an established LTS line and exceeds the current Vite minimum (20.19+ or 22.12+). npm is included with Node and avoids introducing a second package-manager decision.
- **Alternatives considered**: Rebuilding an existing app was not possible because none exists in this repository. Python/backend or monorepo scaffolding would expand the authorized frontend scope.
- **References**: [Vite getting started](https://vite.dev/guide/); [Node.js releases](https://nodejs.org/en/about/previous-releases).

### 2. Navigation and styling

- **Decision**: Use React Router's declarative mode for guarded, refreshable workspace URLs; use plain CSS and a small shared token set.
- **Rationale**: Login, overview, three workspaces, metadata settings, direct navigation, and route guarding are required. Declarative routing provides URL matching/navigation without adopting a full server-rendered framework. Plain CSS is sufficient for the bounded UI and avoids an unneeded UI or styling dependency.
- **Alternatives considered**: One component with local-only tab state would not represent route protection or direct refresh reliably. A full framework, CSS utility system, or component kit has no demonstrated need.
- **Reference**: [React Router modes](https://reactrouter.com/start/modes).

### 3. State and browser persistence

- **Decision**: Keep UI session state in `sessionStorage`, metadata definitions under the exact UI-owned `localStorage` key `hamtayar-demo-ui.metadata.v1`, and operation state/results and drafts in a lightweight in-memory app-level manager across route navigation. Keep Demo fixtures in a separate module from service adapters.
- **Rationale**: This follows the spec's required lifetimes, retains pending operation results across workspace navigation, and lets logout clear temporary state without implying server-side cancellation. A replaceable adapter boundary keeps fixture and HTTP behavior distinct.
- **Alternatives considered**: Persisting drafts, answers, or credentials adds privacy risk and is explicitly outside the requested behavior. A server-side registry/database is a non-goal.

### 4. Behavioral testing

- **Decision**: Use Vitest with React Testing Library and user-event for component and flow behavior; mock the HTTP adapter for deterministic UI tests. Keep real service checks separate and conditional.
- **Rationale**: Vitest is built for the Vite ecosystem; current Vitest requires Node 22.12+ and Vite 6.4+, which Node 24 satisfies. React Testing Library encourages tests that interact with rendered controls as users do. This supports repeatable checks for login, storage, form validation, mode separation, and failure states without calling live services.
- **Alternatives considered**: Snapshot-only tests do not adequately verify user behavior. End-to-end integration tests against absent or incomplete services would falsely imply backend readiness. No browser automation framework is needed for the initial bounded demo; manual responsive/keyboard checks are specified.
- **References**: [Vitest guide](https://vitest.dev/guide/); [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/).

### 5. Formatting and static checks

- **Decision**: Provide explicit npm scripts for Prettier formatting, ESLint linting, TypeScript typechecking, behavior tests, and production build. Pin compatible development-tool versions through the single npm lockfile.
- **Rationale**: The constitution requires repeatable formatter/linter/typecheck/build commands, and no existing toolchain is present. Current typescript-eslint documentation provides a flat-config setup; Prettier is a standalone formatter. Node 24 satisfies Prettier's current Node requirement.
- **Alternatives considered**: Relying on editor-global configuration would make results non-reproducible. Combining all quality checks into an unobservable one-off command would obscure which check failed.
- **References**: [typescript-eslint setup](https://typescript-eslint.io/getting-started/); [Prettier install](https://prettier.io/docs/install.html).

### 6. Safe answer Markdown

- **Decision**: Render answer text with `react-markdown` using its safe defaults; do not enable raw HTML or replace its URL safety transform. Add no plugins unless a specific requirement justifies them and they are separately reviewed.
- **Rationale**: The spec requires Markdown rendering of untrusted service output without executable markup. The library builds React elements and documents that it is safe by default; raw HTML/plugins/custom URL transforms increase the security surface.
- **Alternatives considered**: `dangerouslySetInnerHTML` or an unsanitized Markdown-to-HTML pipeline is not acceptable. Plain text would avoid XSS but would not fulfill the requested Markdown presentation.
- **Reference**: [react-markdown security guidance](https://github.com/remarkjs/react-markdown#security).

### 7. Current Hamtayar service

- **Observed**: The sibling `D:\Hamtayar\hamtayar` source has `POST /api/v1/document-ingestion/jobs`. It accepts a multipart file plus `source_id`, `knowledge_space_id`, `version`, and `processing_profile`; the operation runs synchronously and returns a completed status, source/version, nullable `chunks_indexed`, and optional `request_id`. Supported extensions are PDF, DOCX, TXT, and MD; maximum bytes are configurable. The route has no custom-metadata input. A missing executor produces an unavailable response; a request timeout is not proof of cancellation. Current source paths include `apps/document_ingestion/api/v1/jobs.py` and `apps/document_ingestion/api/schemas/jobs.py`.
- **Observed**: `POST /api/v1/answers` accepts only `question` (1–4096 characters, extra fields forbidden). The current auth dependency fails closed with 401; a missing executor produces 503. It returns actual status, answer, citations, and request ID when execution succeeds. Current source paths include `apps/retrieval/api/v1/answers.py`, `apps/retrieval/api/schemas/answers.py`, and `apps/retrieval/api/dependencies.py`.
- **Decision**: The P1 Demo remains independent. In API mode, ingestion can only offer its fixed supported fields; entered custom metadata requires a clearly disclosed reduced-test action. Q&A with user metadata or filters is blocked unless a future verified contract accepts them; the current UI-only login cannot enable the Answer endpoint.
- **Integration gates**: Confirm deployed URL, browser origin/CORS or local proxy behavior, configured upload limit and timeout, executor readiness, response shape, and any deployment-level authentication before enabling each action. Health reachability alone does not satisfy these gates. Do not edit backend domain behavior in this feature.
- **File validation**: Document picker and drag/drop share the same validator. Demo mode has no artificial size cap and does not read entire file contents for preview. API mode requires the applicable verified per-service limit and blocks submission when unknown; do not substitute a guessed client cap.

### 8. Current CGC/HamtayarDemo service

- **Observed**: `D:\Hamtayar\CGC\HamtayarDemo` exists, contrary to the historical PRD observation. Its README and backend describe local codebase/archive processing, project upload/indexing, status/logs, and additional search/context/chat capabilities. The current upload path can return HTTP 202 followed by status polling; a legacy multipart route remains. The service has dependencies on the CGC executable and staging/destination Neo4j configuration. Its README explicitly warns against network exposure without authentication/authorization.
- **Decision**: The P1 Codebase workspace uses local fixtures. API-mode Codebase remains gated until the exact endpoint sequence, request/response fields, polling semantics, archive limits, local host, and dependencies are verified against the intended running configuration. Use only explicitly configured loopback/local addresses; do not make network exposure or auth changes to CGC part of this UI feature.
- **Integration gates**: Validate capability/diagnostic information, configured CGC executable, both database targets, supported archive formats and limits, CORS/proxy behavior, and safe local-only reachability. Treat route existence or health as insufficient proof that indexing works.

### 9. Frontend security and network boundary

- **Decision**: Read non-secret service addresses and timeout settings from `.env.local` through one shared typed configuration module and HTTP client. Do not put service credentials or provider secrets in environment values that are bundled for browsers. Keep the demo password out of persisted storage and mask it in UI diagnostics. Use local-only defaults for the unauthenticated CGC service.
- **Rationale**: Browser-delivered values are observable by users, and the current CGC service documents a local-only trust boundary. The frontend demo account is not trusted backend identity.
- **Alternatives considered**: Adding proxy authentication or backend services would violate the feature's frontend-only ownership and is not necessary for the P1 demo.

## Research status

No technology choice remains unresolved. API integration work is conditional on the service verification gates above and does not block the P1 implementation plan.
