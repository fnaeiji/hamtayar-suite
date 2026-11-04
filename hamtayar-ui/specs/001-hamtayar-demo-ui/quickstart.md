# Quickstart and Validation Guide

This guide is the planned implementation's local run and acceptance checklist. It does not claim the UI or integrations are implemented yet.

## Prerequisites

- Windows with PowerShell and Node.js 24 LTS (npm included).
- The UI repository at `D:\Hamtayar\hamtayar-ui`.
- Hamtayar and CGC/HamtayarDemo are optional for all Demo-mode checks.
- For API checks only: a deliberately configured local service, verified API contracts, required executors/dependencies, and any approved local proxy/CORS setup. Do not expose unauthenticated CGC/HamtayarDemo to a network.

## Setup and run

```powershell
Set-Location D:\Hamtayar\hamtayar-ui
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open the local URL printed by the development server. Use the fixed demo credentials from the specification. `.env.example` should contain non-secret service addresses/timeouts and any required verified API upload limit; omit `.env.local` from version control.

## Repeatable P1 Demo checks

1. Stop or leave all services unavailable. Sign in with valid credentials; verify invalid credentials fail, refresh retains the tab session, and logout returns to login.
2. In Demo mode, visit Codebase, Document Ingestion, and Q&A. Run each fixture flow and verify the simulated label; inspect browser network activity to confirm no operational requests were sent. Use the same validator for document selection and drag/drop; Demo mode has no artificial size cap.
3. Add a filterable document select field. Verify it appears in the document form and Q&A filter controls and persists under localStorage key `hamtayar-demo-ui.metadata.v1` after refresh/restart; verify Restore defaults leaves unrelated localStorage keys unchanged.
4. Verify duplicate/reserved keys and invalid options are rejected; verify required numeric `0` and boolean `false` pass; verify persistence failure is disclosed if reproducible.
5. Submit multiple Demo documents with distinct metadata and verify independent outcomes. Confirm navigating to another workspace and back retains a pending operation result; mode switching is disabled while pending and clears transient results afterward; logout clears temporary data.
6. At 1366×768 and 390px, check page overflow, navigation, focus visibility, labels, and keyboard-only operation. Inspect LTR identifiers/JSON inside RTL content.

## API checks (conditional)

1. Configure only an explicitly approved local base address. Verify reachability separately from each operation's readiness.
2. For ingestion, verify fixed-field request mapping and actual response fields. Confirm the per-service upload limit against the deployed service and configure it before enabling submission; block submission if unknown. With custom metadata present, confirm the full request is blocked unless the operator selects the explicit reduced test action. Test one-file failure alongside a separate success and do not retry timeouts automatically.
3. For Q&A, verify only a question-only request can be offered against the observed contract; current 401/503 responses remain blockers and do not trigger fixtures.
4. For Codebase, first pass all gates in [cgc-local-api.md](contracts/cgc-local-api.md). Verify actual upload/status/log semantics and local-only exposure before enabling actions.
5. Confirm diagnostics show sanitized intended/transmitted data and actual responses, never secrets, fabricated IDs, fake progress, or unsupported citations.

## Commands to run after implementation

```powershell
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
```

Record command output and environment in the delivery report. Report blocked or unrun checks honestly; mocked adapter tests are not end-to-end integration results.
