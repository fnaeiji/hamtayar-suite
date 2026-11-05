# Current decisions

- Reuse original CGC frontend sources as a same-server HTML entry. This avoids a second frontend port, copied business screens and style collisions while preserving source explorer/graph/context/settings functionality.
- Parent routes and code UI share a page-key inventory. Only same-origin messages from the exact expected window are accepted; payloads cannot supply endpoint URLs or arbitrary commands.
- Preserve backend Origin validation. Extend its explicit local allowlist instead of stripping Origin or introducing a wildcard. Restrict Vite proxy targets to local HTTP(S) origins.
- Phrase search is actual local UTF-8 text matching, not invented Qdrant/FTS integration. A 2 MiB per-file memory budget avoids reading arbitrary large selected files. Unsupported formats remain visible with a reason.
- Replace the previous configurable metadata editor with the user's current fixed profile and pure validators. Retain old browser data without consuming it.
- Keep service authentication and manually selected access levels separate. Neither demo login nor a classification select creates a trusted Padeen authorization scope.
- A single browser address does not eliminate Python, CGC or Neo4j processes. The launcher coordinates existing processes; readiness still requires real environment evidence.
