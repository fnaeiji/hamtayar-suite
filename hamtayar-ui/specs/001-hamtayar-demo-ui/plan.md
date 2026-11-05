# Plan: Unified Hamtayar Demo

React/strict TypeScript/Vite main application with locally bundled fonts. Existing CGC frontend remains in `CGC/HamtayarDemo/frontend/src`; do not duplicate its application or graph code.

## Boundaries

- `src/app`: shared four-workspace catalog, routing, shell and protected demo session.
- `src/features/documents`, `qa`, `search`: current product pages and their small pure models/services.
- `src/services/documentCatalog.ts`: successful session registrations, derived centers and bounded local UTF-8 text copies.
- `src/services/metadata/values.ts`: pure validation/filtering, replacing obsolete editor/storage service.
- `src/features/codebase`: typed shared navigation bridge and same-origin code frame host.
- `code/index.html`, `code/entry.ts`: second Vite HTML entry importing original CGC UI plus local fonts.
- `vite.config.ts`: explicit React/graph dependency resolution for sibling sources, narrow filesystem allowlist, dev/preview local proxy.
- `scripts/start-demo.ps1`: start the already configured CGC Python backend and one frontend, owning only its own child process.

## Integration decisions

A same-origin frame retains the complete existing code UI and CSS isolation. It is not an external-port link or a duplicate implementation. Route `/codebase/:view` exchanges only whitelisted page keys with that frame and preserves its runtime between submenus. Leaving code/logging out unmounts the frame; backend processing may continue.

Embedded code requests `/code-api`, rewritten to existing backend `/api`; preserve browser Origin and extend the backend guard with exact local dev/preview origins. Bind frontend/backend to loopback. Existing CGC endpoints, jobs and storage remain authoritative.

## Cleanup

Remove the no-longer-routed metadata editor and persistence service/tests, placeholder, old code fixture/service, unused common components, external code-URL configuration and readiness stub. Keep active Spec Kit tooling, original PRD, working API adapters and relevant behavioral tests. Consolidate source registrations/centers into one catalog and remove redundant observers/shared override state.

## Verification

Run format, lint, strict main TS, current Vitest suite and both-entry production build. Exercise the unified browser flow with a fixture backend through the actual Vite proxy, checking same-origin navigation, retained project/settings, literal local search and desktop/mobile overflow. Separately disclose that Windows launcher and live services require the user's environment. See current docs/verification.md.
