# Implementation Plan: Hamtayar Demo UI

**Branch**: `001-hamtayar-demo-ui` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-hamtayar-demo-ui/spec.md`

## Summary

Create a new, local-first Persian RTL dashboard in the currently documentation-only `hamtayar-ui` repository. The P1 release is a complete, clearly labeled fixture-based demo for login, metadata settings, document ingestion, Q&A, and codebase processing. API mode is an opt-in set of replaceable clients that call only verified existing operations, show actual results, and block unsupported payloads or unavailable authorization. No backend domain work is planned.

## Technical Context

**Language/Version**: TypeScript with strict checking; Node.js 24 LTS for local development/build.

**Primary Dependencies**: React and Vite as required by the project constitution; React Router for navigable guarded workspaces; `react-markdown` for safe answer rendering; Vitest and React Testing Library for behavior-focused tests; ESLint and Prettier for repeatable lint/format commands. Use plain CSS and native browser APIs; add no UI kit or state-management framework without a demonstrated need.

**Storage**: `sessionStorage` for the tab-scoped demo session; `localStorage` key `hamtayar-demo-ui.metadata.v1` only for metadata field definitions; operation state/results and drafts remain in an in-memory app-level manager across workspace navigation. Restore defaults changes only the namespaced key. Logout clears temporary state and stops local observers. No server-side storage or persistent job system is introduced.

**Testing**: Vitest + React Testing Library for validation, metadata, mode, operation, and accessible user-flow behavior; mocked adapters for client tests; manual browser checks for RTL, responsive widths, keyboard/focus, and real configured service calls. Provide repeatable `format`, `lint`, `typecheck`, `test`, and production `build` commands; report real results.

**Target Platform**: Current desktop and mobile browsers, locally served over HTTP during the demo; validate at 1366×768 and 390px width.

**Project Type**: Single frontend web application; sibling Hamtayar and CGC services remain external dependencies.

**Performance Goals**: Local navigation and metadata edits respond within one second on the documented test machine; service latency is reported separately and is not included in this target.

**Constraints**: Persian RTL UI with LTR treatment for identifiers/JSON; no real credentials or provider secrets in client bundles; non-secret service addresses/timeouts and any required verified upload limits come from `.env.local` through one shared typed configuration module; no Demo-mode operational requests or artificial Demo file-size cap; API upload is blocked until its per-service limit is verified; no auth bypass, guessed endpoints, fake API fallback, or backend domain changes. CGC/HamtayarDemo is documented as local and unauthenticated, so codebase API access must remain explicitly configured for local use and must not expose that service to a network.

**Scale/Scope**: One presenter/tester session; five workspace destinations plus logout; three independent workspaces; small configurable metadata definitions and multiple independently submitted documents. No production multi-user or high-volume requirements.

## Constitution Check

**Gate before research: PASS.**

| Principle / gate | Plan evidence |
|---|---|
| I. Small scope and maintainable structure | One frontend project with only dependencies needed for routes and user-facing tests; no speculative infrastructure. |
| II. Frontend component boundaries | Pages coordinate presentation; shared components receive clear inputs; service clients, fixtures, metadata settings, and types remain outside pages. |
| III. TypeScript and data contracts | Strict TypeScript; explicit UI models and API DTO mapping; unknown network data is validated before display. |
| IV. Persian visual consistency | Persian RTL as the default, a small shared token set, and LTR handling for technical values. |
| V. Accessibility and predictable behavior | Labeled controls, visible keyboard focus, responsive navigation, and explicit empty/loading/success/error states. |
| VI. State ownership and lifecycle | Session, settings, drafts, and operation results have separate owners and lifetimes; pending requests prevent duplicate submits and mode changes. |
| VII. Dynamic forms and local settings | One metadata definition model drives document/user fields and filters; persistence failure is visible; reserved keys are rejected. |
| VIII. Hardcoded demo login | Fixed credentials gate only the UI and are not presented as service authentication; password is not persisted. |
| IX. Honest Demo/API separation | Demo uses fixtures without operational calls; API results come only from actual responses; mode changes clear transient results. |
| X. Upload, async requests, and errors | Per-file outcomes, no automatic upload retries, uncertain timeout semantics, sanitized errors, and stale/pending request handling. |
| XI. Proportionate performance/tooling | No premature optimization; measure local response on the documented machine; maintain a single package manager/lockfile. |
| XII. Behavioral tests and reproducible evidence | Tests cover user behavior, mapping, storage, mode boundaries, and failures; verification results are reported accurately. |

**Gate after design: PASS, subject to the explicit external-service conditions in this plan.** No new service, database, backend domain change, or unverified operation is required for the P1 demo. Real API actions remain disabled until the matching contract and dependencies are verified.

## Research Decisions

See [research.md](research.md). Key decisions are to start with React + TypeScript + Vite, use Node.js 24 LTS for ecosystem maturity, use plain CSS, separate fixtures from API adapters, and treat current Hamtayar/CGC observations as conditional integration contracts rather than permission to expand backend scope.

## Project Structure

### Documentation (this feature)

```text
specs/001-hamtayar-demo-ui/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── hamtayar-api.md
│   ├── cgc-local-api.md
│   └── ui-behavior.md
└── tasks.md              # Created by $speckit-tasks, not this command
```

### Source Code (repository root)

```text
src/
├── app/                   # App shell, route guards, mode state
├── components/            # Shared navigation, forms, status, diagnostics
├── features/
│   ├── auth/               # UI-only demo session
│   ├── overview/
│   ├── metadata/
│   ├── documents/
│   ├── qa/
│   └── codebase/
├── services/
│   ├── api/
│   │   ├── httpClient.ts   # Shared HTTP transport
│   │   └── adapters/       # Replaceable service adapters and explicit DTO mapping
│   ├── operations/
│   │   └── operationManager.ts # In-memory lifecycle across workspace routes
│   └── metadata/           # Definition persistence and validation
├── fixtures/               # Labeled Demo-mode sample inputs/results
├── config/
│   └── services.ts         # Typed non-secret .env.local service URLs/timeouts
├── types/                  # Shared UI models and API DTOs
└── styles/                 # RTL base styles and shared design tokens

tests/
├── unit/                   # Validators, mapping, storage, formatting
├── components/             # Accessible interaction behavior
└── flows/                  # Login, mode isolation, workspace journeys
```

**Structure Decision**: The repository contains no app source, package manifest, lockfile, README, or test harness, so this is a new single-project frontend. The proposed layout follows the constitution and PRD without adding a backend subproject. A single root package manifest and lockfile own the UI. UI tests mock service adapters; separate real integration checks are run only when services are configured and available.

## Phase 0: Research

Research is recorded in [research.md](research.md). It resolves every plan-level technology choice and documents the current, conditional service integration findings. No unresolved implementation decision requires user clarification.

## Phase 1: Design & Contracts

- [Data model](data-model.md) records demo session, field definition, drafts, operation state, and result lifecycle/validation.
- [Hamtayar API contract](contracts/hamtayar-api.md) records the observed ingestion and Q&A limits and explicit blocked behaviors.
- [CGC local API contract](contracts/cgc-local-api.md) records the observed candidate API and local-only security/dependency gates; operations are not enabled merely because routes exist.
- [UI behavior contract](contracts/ui-behavior.md) defines the interaction boundary for Demo/API, metadata-driven fields, and truthful diagnostics.
- [Quickstart](quickstart.md) documents setup and repeatable P1 validation plus conditional API checks.

## Complexity Tracking

No constitution violations. No extra project, service, persistence layer, or API is introduced. React Router is justified by guarded workspace navigation and refreshable destinations; Vitest/React Testing Library are justified by the required repeatable user-behavior checks.
