# CGC/HamtayarDemo Local API Contract (Candidate)

**Evidence date**: 2026-11-04. `D:\Hamtayar\CGC\HamtayarDemo` exists and has a FastAPI service and local React UI. This document is an integration gate, not approval to enable every discovered route.

## Current observations

- The service exposes health/capability/diagnostic information and project/archive operations, including upload, indexing, status, logs, source, search, graph, context, and chat.
- The documented current upload path accepts raw archive bytes at `POST /api/projects/upload?filename=project.zip`, returns HTTP 202, and requires later status polling. The legacy multipart `POST /api/projects` route is synchronous.
- The service is described as local and unauthenticated. Its README explicitly says not to expose it to a network without authentication/authorization.
- Indexing depends on the CGC executable and both staging and destination Neo4j targets. A health check or successful database connection does not prove indexing/publication works.
- The service has archive limits, extraction policies, optional external tools, and runtime state. These must be read from the current service capability/settings response rather than duplicated as assumed constants in the UI.

## API-mode enablement gates

Before enabling upload/index/status/log UI actions:

1. Confirm the exact running service version and endpoint sequence against its OpenAPI/capability/diagnostic output and source documentation.
2. Verify archive types and configured compressed/expanded limits, request body behavior, status lifecycle, cancellation semantics, log limits, and returned identifiers.
3. Verify CGC executable readiness and both Neo4j connections and confirm a controlled operation can reach the intended completion state.
4. Confirm browser CORS or local proxy configuration and constrain the configured target to an explicit local/loopback address; do not expose or proxy the unauthenticated service onto a network.
5. Map only actual fields and statuses. Do not show fabricated progress, stages, logs, or completion. Preserve uncertain states after network loss.

Until all gates pass, show an unavailable/blocked explanation in API mode and keep the P1 fixture demonstration usable. Do not change CGC service code, authentication, network exposure, database behavior, or indexing workflows in this feature.

## Evidence

- `D:\Hamtayar\CGC\HamtayarDemo\README.md`
- `D:\Hamtayar\CGC\HamtayarDemo\backend\app\main.py`

## Delivery evidence — 2026-11-04

No running CGC target was supplied or verified in this execution environment.
OpenAPI/capability/diagnostic output, executable, both Neo4j targets, archive limits,
CORS and completion semantics remain unverified. The client only implements a
loopback/readiness blocker and does not send archive/index/status requests.
See `../../../docs/integration-map.md`. T037 remains open.
