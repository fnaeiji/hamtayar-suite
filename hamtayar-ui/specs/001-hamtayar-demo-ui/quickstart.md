# Quickstart

The current run instructions are in [README.md](../../README.md).

1. Stop old frontend processes, install from `hamtayar-ui` with `npm ci`.
2. For document/Q&A/phrase Demo only, use `npm run dev`.
3. For all workspaces with a configured CGC environment, use `scripts/start-demo.ps1`; do not start the old CGC frontend.
4. Open only `http://127.0.0.1:5174`; log in with `demo` / `Hamtayar123!`.
5. Register a UTF-8 TXT/Markdown with center/type, then search for a literal phrase with metadata filters.
6. Open codebase and navigate its submenus; native code operations require its Python backend and dependencies.
7. Run automated checks and `npm run test:browser`; the latter uses a fixture backend, not real databases or model calls.

Local files/results are session memory and clear on logout/mode switch/reload. The current integration/readiness boundaries are documented in `docs/integration-map.md`.
