# Integration map — 2026-11-05

| Operation                        | State                               | Evidence / limitation                                                                                     |
| -------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Document Demo                    | Local only                          | Successful fixture operation; bounded local text copy for phrase search; no backend ingestion             |
| Q&A Demo                         | Demo only                           | Fixed labeled answer/citations; no retrieval or model call                                                |
| Phrase search                    | Local only                          | Actual literal matches in uploaded session TXT/Markdown with metadata filters                             |
| Hamtayar ingestion adapter       | Adapter only                        | Existing exact multipart mapping tested with mocked transport; live readiness still blocked               |
| Hamtayar answers adapter         | Blocked                             | Question-only request; current source authentication fails closed with 401                                |
| Code UI integration              | Browser tested with fixture backend | Original code application, shared submenus, same-origin proxy, preserved project/settings across submenus |
| CGC / Neo4j / provider execution | Not live-verified here              | Depends on the user's configured backend, executable, both databases and provider settings                |

The main UI serves at 5174, or built preview at 4173. `/code/index.html` is an entry in that same frontend, not an external UI link. `/code-api` forwards to backend `/api` (default loopback 8000). The user's Python processing service is still required; a single UI origin is not a single process.

Code transport behavior is retained: raw ZIP/RAR upload, polling, source, graph, search, context, reports and settings are owned by the existing HamtayarDemo. No replacement domain API, database writes or workflow is invented by the main dashboard. The new allowed backend origins are exact local 5174/4173 values; existing local origins remain.

Backend fixtures in automated browser checks are not evidence of live indexing, Neo4j connectivity or provider readiness. Keep existing Hamtayar API gates and exact DTO mapping: custom metadata is never silently forwarded or dropped, and descriptive access level never grants trusted Padeen permissions.
