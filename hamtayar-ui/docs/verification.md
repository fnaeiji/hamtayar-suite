# Verification — 2026-11-05

This report describes the current unified application, replacing earlier revision logs.

Environment: Linux, Node 24.22.1, npm 11.9.0; Chromium 134 via Playwright 1.51.1.

## Completed checks

- Main frontend: formatting, ESLint, strict TypeScript and production multi-entry build.
- Current unit/component suite: **44 tests passed across 15 files**; includes authentication, operation lifecycle, independent document results, current metadata profile, catalog registration, local phrase filtering, sanitized adapters and code frame messaging.
- Real browser flow: login → local UTF-8 TXT registration → literal phrase match with center/classification → code workspace → source → graph → settings → code search → settings.
- Browser fixture flow passed for both `npm run dev` and the compiled `npm run preview` build. The browser fixture test verifies the actual Vite `/code-api` proxy rewrite to `/api`, preserves the browser Origin on POST, retains the selected code project and unsaved settings between submenus, and makes no external-origin requests.
- Desktop 1366×768 and mobile width 390 checked for page-level overflow; embedded mobile content also checked. Screenshots reviewed for overview, phrase results, graph and code settings.
- No browser page errors in the verified flow. Original graph canvas mounted successfully with fixture nodes/edges.

The obsolete metadata settings/persistence and readiness-stub tests were removed with their deleted implementation; replacement tests cover the active profile, catalog and unified boundaries. Test counts refer to the current suite, not an accumulating historical total.

## Limits

The browser fixture backend is not the real Python/CGC service. Live indexing/publication, both Neo4j connections and provider calls were not exercised. The PowerShell startup script was inspected but cannot be executed in this Linux environment. Main `npm run typecheck` checks the main application and shared navigation; the existing CGC frontend source is bundled as its own HTML entry rather than silently included in the main app's strict TS project.

Source/backend transport change: the existing local browser guard now explicitly permits 5174 and preview 4173. Python syntax compilation was checked; full backend runtime tests require that service's dependencies/environment.

Run `npm test` for the current unit count and `npm run test:browser` for reproducible fixture-backed UI verification. Browser screenshots are generated under ignored `runtime/browser-check`.
