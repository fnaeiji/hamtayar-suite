# Hamtayar API Integration Contract (Observed)

**Evidence date**: 2026-11-04. Source code was inspected in sibling `D:\Hamtayar\hamtayar`. Confirm the running deployment matches these observations before enabling an operation.

## Document ingestion

- **Method/path**: `POST /api/v1/document-ingestion/jobs`
- **Request**: multipart form with `file`, `source_id` (1–128 characters, constrained identifier pattern), `knowledge_space_id` (same), `version` (same), and optional `processing_profile` (1–64 characters; default `default`).
- **Formats**: PDF, DOCX, TXT, Markdown. The service checks filename/content-type and basic file signature/UTF-8. The configured byte limit is read from service settings; the client must verify the deployed value.
- **Execution**: Synchronous. HTTP 200 means processing completed before the response was sent. A missing executor or timeout is an error, not a queued job guarantee.
- **Response**: `status: "completed"`, `source_id`, `version`, nullable `chunks_indexed`, optional `request_id`.
- **Metadata boundary**: No custom metadata fields are accepted by the observed route. UI metadata cannot be silently dropped or claimed as indexed. Require a clearly named reduced-test confirmation before sending fixed fields without custom metadata.
- **Retry boundary**: The service can return a timeout after processing may have started. Do not automatically retry; preserve source identity and describe completion as uncertain after client connection loss.
- **Client behavior**: One request per selected file, with independent request state. Map only actual response fields. Display null chunk count as “گزارش نشده”.

## Answer

- **Method/path**: `POST /api/v1/answers`
- **Request**: JSON `{ "question": string }`, 1–4096 characters after trimming; extra fields are rejected.
- **Authorization**: Current auth dependency fails closed with 401 because trusted identity integration is not implemented. Demo credentials are not bearer credentials and must never be forwarded or used to bypass this check.
- **Availability**: Missing answer executor returns 503; timeout and provider failures are distinct errors.
- **Response**: Actual `status`, `answer`, `citations`, `request_id`. Do not synthesize citations or treat an empty/no-evidence result as provider failure.
- **Metadata/filter boundary**: User metadata and filters are not accepted by this observed public request. Block a full personalized/filtered submission. The explicit question-only test action may be offered only with a pre-submit disclosure; label the answer as unfiltered and non-personalized.

## Shared conditions and enablement gates

- Keep health/reachability separate from per-operation availability.
- Before API actions are enabled, confirm service base address, deployed schema/version, browser CORS or same-origin proxy, configured limits/timeouts, executor readiness, and any reverse-proxy authentication.
- Never place service/provider secrets in browser configuration. No backend contract change is part of this feature.
- In tests, mock the client boundary. Do not label fixture/mock results as real integration.

## Evidence paths

- `D:\Hamtayar\hamtayar\apps\document_ingestion\api\v1\jobs.py`
- `D:\Hamtayar\hamtayar\apps\document_ingestion\api\schemas\jobs.py`
- `D:\Hamtayar\hamtayar\apps\retrieval\api\v1\answers.py`
- `D:\Hamtayar\hamtayar\apps\retrieval\api\schemas\answers.py`
- `D:\Hamtayar\hamtayar\apps\retrieval\api\dependencies.py`
