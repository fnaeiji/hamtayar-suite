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
