# Verification — 2026-11-04

Environment: Linux, Node 24.22.1, npm 11.9.0. Installed versions are captured in
`package-lock.json`. Tests use Vitest and jsdom; they are not a real browser session.

| Check                                                 | Observed result                                                                                    |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `npm run format:check`                                | Passed                                                                                             |
| `npm run lint`                                        | Passed                                                                                             |
| `npm run typecheck`                                   | Passed                                                                                             |
| `npm test`                                            | 49 tests passed in 13 files                                                                        |
| `npm run build`                                       | Passed; 236 modules transformed                                                                    |
| `npm run preview` HTTP smoke                          | HTTP 200, built HTML references compiled JS/CSS                                                    |
| 1366×768 and 390px browser visual/keyboard checks     | Not run: no Chromium executable; Playwright browser download returned an invalid/truncated archive |
| Real service integration                              | Not run; deployment readiness and authentication unavailable                                       |
| Moderated acceptance / subsecond metadata performance | Not measured                                                                                       |

The initial baseline test run passed 21 existing tests but failed four suites on
missing document/Q&A/codebase/Markdown modules. These suites now pass. The original
document test used an asymmetric matcher unsupported by `toHaveValue`; it now checks
the input's `value` property while preserving the assertion of a nonempty suggested ID.

Behavioral coverage includes login/navigation, refresh session, storage failures,
metadata persistence/restore boundaries, shared/per-file overrides, independent
file failures, unknown API limit, no operational fetches in each Demo workspace,
full login-to-document operation with navigation while pending, pending mode lock,
late-response rejection, repeated mode/logout cleanup, typed filters including
zero/false, explicit unset booleans, retained question on errors, safe Markdown,
exact multipart/question-only mapping, invalid response rejection, HTTP errors,
network/timeout distinction, uncertain upload outcome, secret-field redaction,
and local-only CGC blocking.

Only UI source/configuration/tests/documentation were changed. Generated output and
node_modules are excluded. Existing source formatting was normalized to make the
repository's formatter check pass; Spec Kit generated/reference documents retain
their upstream formatting.

## Open gates

- T035: intended running service settings cannot be inspected here. The integration
  map records every classification and blocker, but live readiness is unverified.
- T037: CGC OpenAPI, capabilities, executable, two Neo4j instances, CORS, archive
  limits and controlled completion remain unverified. API controls stay disabled.
- T043: responsive CSS and accessible controls implemented; actual browser layout,
  focus, keyboard and target viewport checks remain pending.
- T044: all automated commands and preview HTTP smoke pass; complete interactive
  quickstart verification remains pending alongside T043. No full acceptance claim.

## UI revision verification — 2026-11-04

- 51 tests passed across 14 files, including exact visible profile, stale-field
  omission, removed settings navigation, code UI link and URL validation.
- Existing metadata settings unit tests still run, though that page is no longer routed.
- Code UI destination/port and visual palette were read from the repository's
  `CGC/HamtayarDemo/frontend/src/style.css`, `README.md` and `scripts/start-dev.ps1`.
- Browser visual checks and real HamtayarDemo navigation on the user's computer
  remain unverified; the earlier browser-runtime limitation still applies.

## Latest classification revision

53 tests pass across 14 files. New/updated flow coverage verifies no shared metadata
fieldset, independent file centers, all three classification options, exactly two
prompt metadata selects, intended document_type mapping, successful-only center
registration, whitespace deduplication, failed-center exclusion, survival after draft
clear/navigation, empty-list guidance and logout reset. This remains a Demo/session
registry and does not establish backend storage or permission enforcement.
Format, lint, TypeScript and production build pass. Browser visual/live API checks
remain unverified as described above.

## Latest formal theme and typography revision — 2026-11-04

This entry supersedes the earlier main-UI browser-runtime blocker. A working
Chromium 134 headless shell was installed and used through Playwright.

| Browser check                       | Result                                                                                                               |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Login at 1366×768                   | Screenshot reviewed; first Tab focuses username; bundled Vazirmatn loads                                             |
| Overview at 1366×768 and 390px      | Screenshots reviewed; no page-level horizontal overflow                                                              |
| Document form at 1366×768 and 390px | Long PDF name, required center/classification and successful Demo registration exercised; no page-level overflow     |
| Q&A at 1366×768 and 390px           | Registered center and access-level selects, question submission and fixture result exercised; no page-level overflow |
| Font/network                        | Actual Vazirmatn loaded; zero external HTTP requests during Demo browser flow                                        |
| Runtime                             | Zero browser page errors in the exercised flow                                                                       |

The main palette uses white cards, a light neutral canvas and navy navigation/hero
for continuity with the separate code workspace. Fontsource supplies locally served
Vazirmatn 400/500/600/700 fonts with swap behavior. No Google Fonts request is used
by the main UI. Screenshots were inspected at desktop and mobile widths.

53 tests across 14 files, formatting, lint, strict TypeScript and production build
pass. CGC's two branding files were checked for the requested visible/browser/footer
labels and its TSX parsed successfully with esbuild; no full CGC runtime or backend
validation was performed. This is a branding-only edit to that frontend.
