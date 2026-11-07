# CGC integration boundary

The existing `CGC/HamtayarDemo/frontend/src` application remains the client owner of upload, indexing, publication, polling, source, search, graph, context, reports and settings. The main UI does not create replacement endpoint contracts.

The embedded client changes only its transport prefix from `/api` to `/code-api`; Vite rewrites that prefix back to backend `/api`. Native raw ZIP/RAR uploads, identifiers, returned statuses/logs, limits and configured services remain authoritative. The main sidebar communicates only page navigation, not backend actions.

The backend's local Origin guard explicitly accepts main UI 5174 and preview 4173 on loopback; prior local values remain allowed. The proxy target is validated as a loopback origin, incoming Origin is not stripped, and the listener is not exposed publicly.

Fixture browser checks verify transport/navigation boundaries, not CGC executable, archive decoding, both Neo4j targets, model connectivity or successful publication. Those require the user's live environment and controlled acceptance run. No graph/workflow/database/auth redesign is included.
