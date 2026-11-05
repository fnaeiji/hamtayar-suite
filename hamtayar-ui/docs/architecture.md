# Current architecture

The main application has four workspaces, one session-only document catalog and one browser origin. There is no second frontend server.

| Responsibility                                        | Owner                                                          |
| ----------------------------------------------------- | -------------------------------------------------------------- |
| Shell, navigation, four workspace descriptions        | `src/app`                                                      |
| Document registration, answers, literal phrase search | `src/features/documents`, `qa`, `search`                       |
| Document text, centers and source identities          | `src/services/documentCatalog.ts`                              |
| Current metadata profile and value validation         | `src/config/demoProfile.ts`, `src/services/metadata/values.ts` |
| Native code UI and graph implementation               | Existing `CGC/HamtayarDemo/frontend/src`                       |
| Same-origin code entry and proxy                      | `code/index.html`, `code/entry.ts`, `vite.config.ts`           |

## Code integration

Vite builds two HTML entries from the same server/build. The main React dashboard embeds `/code/index.html?embedded=1` inside `/codebase/:view`. This preserves the existing code application and isolates its CSS/runtime without copying its screens or running another Vite server. The old standalone entry still works if needed, but is not required by the unified workflow.

Navigation is shared through `CGC/HamtayarDemo/frontend/src/navigation.ts`. Parent/child messages carry only whitelisted page keys and are checked against both exact origin and window identity. The frame remains mounted across code submenus, preserving selected project and entered settings. Leaving the code workspace or logging out destroys it and stops browser-local polling; this is not a service-side cancellation guarantee.

The embedded API client sends to `/code-api`, which Vite rewrites to the existing backend `/api`. Both dev and preview proxies accept only an explicit loopback origin. Incoming browser Origin is preserved. The backend local-origin guard explicitly permits the new dev and preview origins; no wildcard, public listener or auth bypass is added. The backend, CGC and Neo4j remain independent processes/services.

## Session data and search

Successful Demo document operations add records to the shared in-memory catalog. TXT/Markdown up to 2 MiB are decoded as UTF-8; other files retain a clear search-unavailable reason. Reads obey operation/session aborts. Source ID replaces a deliberate retry rather than duplicating the record. Centers are normalized and derived from successful catalog records.

Phrase search is literal, case-insensitive and applies center plus classification equality together. Snippets are rendered as React text with a `mark` element, not raw HTML. No SQL/Cypher or operational request is generated. No preview, answer or text content is persisted to localStorage.

## Cleanup

Removed the previous metadata settings page and its persistence/editor service/tests; unreachable placeholder; old codebase fixture/service; unused loading/connection/LTR components; separate-code-URL config; obsolete CGC readiness adapter/tests; redundant draft metadata observers, shared override state and editor CSS. Current value validation is a small pure module. Active Spec Kit tooling and source requirements remain as project governance, not runtime code.
