# Data Model: Hamtayar Demo UI

This model describes browser-visible UI state. It does not create a server-side registry, grant permissions, or claim API acceptance of UI-only fields.

## DemoSession

Represents the UI-only signed-in state for the current browser tab.

| Field | Meaning / validation | Lifetime |
|---|---|---|
| `signedIn` | Boolean set only after fixed demo credential comparison. | Tab session |
| `createdAt` | Optional diagnostic timestamp; contains no credential. | Tab session |

**Transitions**: `signedOut → signedIn` after valid credentials; invalid credentials leave the state unchanged; `signedIn → signedOut` on logout. A refresh retains signed-in state for the tab. This state is never sent as trusted API authentication.

## MetadataFieldDefinition

One configurable field used by document forms, descriptive-user forms, or query filters.

| Field | Meaning / validation |
|---|---|
| `key` | Unique stable English identifier; reject malformed and reserved system/security keys. |
| `labelFa` | Persian label shown to the operator. |
| `group` | `document` or `user`. |
| `type` | `text`, `number`, `boolean`, `select`, or `multi_select`. |
| `options` | Stable English values and Persian labels for selection types; required and unique where applicable. |
| `required` | Required for supported form submissions; document-required does not imply query-required. |
| `enabled` | Disabled fields are excluded from forms and submissions. |
| `visibleInForm` | Controls form visibility; hidden fields do not contribute stale values. |
| `filterable` | Applies to document fields and controls whether a query filter is offered. |

**Validation**: Keys are unique; reserved names include `tenant_id`, `acl_principals`, `principals`, `access_scope`, and `subject_id`. Options must be valid for selection types. `0` and `false` count as supplied values. Default definitions are `department`, `project`, `document_type`, `tags`, `display_name`, `expertise`, and `answer_language` as specified in FR-018.

**Persistence**: Stored under the exact UI-owned localStorage key `hamtayar-demo-ui.metadata.v1` across refresh/restart. Restore defaults changes only that key and never clears unrelated browser storage. If read/write fails or stored data is invalid, report the issue and continue with validated in-memory defaults; never claim a failed write succeeded.

## DocumentDraft and DocumentOperation

Each selected file has an independent draft and outcome.

| Field | Meaning / validation |
|---|---|
| `file` | Browser file handle/reference; content is not persisted. |
| `sourceId` | Editable stable identity, initially suggested as a UUID; retained for deliberate retry. |
| `knowledgeSpaceId` | Required fixed service field. |
| `version` | Required fixed service field. |
| `processingProfile` | Required/configured service field; API default must follow the actual contract. |
| `customMetadata` | Values for enabled document definitions; kept distinct from fixed endpoint fields. |
| `mode` | `demo` or `api`; captured when operation starts. |
| `status` | `idle`, `validating`, `pending`, `completed`, `failed`, or `uncertain`; fixture statuses are explicitly simulated. |
| `result` | Actual response fields or labeled fixture output, never a merged/fabricated result. |
| `diagnostics` | Sanitized intended/transmitted payload, response, elapsed time, and supplied request ID where available. |

**Transitions**: `idle → validating → pending → completed/failed/uncertain`. A second submit is rejected while pending. Ingestion is never automatically retried; timeout/connection loss may leave a server-side outcome uncertain. One file's transition does not modify another file's draft/result.

**File validation**: File selection and drag/drop use the same type/size validator. Demo mode has no artificial size cap and does not read the entire file into memory. API mode uses only the verified limit for that service and blocks submission when the limit is unknown.

## QueryDraft

| Field | Meaning / validation |
|---|---|
| `question` | Required trimmed string; service currently allows 1–4096 characters. |
| `userMetadata` | Values for enabled descriptive-user definitions; not verified identity. |
| `filters` | Values from enabled, visible, filterable document definitions. One selected value means equality; multiple values mean any-of; fields combine with AND. |
| `mode` | Captured `demo` or `api` mode. |
| `result` | Actual API response or clearly labeled sample answer/citations. |

Unset values are omitted; `0`/`false` remain values. The UI request model does not imply that the current answer endpoint accepts metadata or filters; its wire contract currently accepts only `question`.

## CodebaseDraft and CodebaseOperation

| Field | Meaning / validation |
|---|---|
| `archive` | Selected archive reference; contents remain in memory until cleared/refreshed. |
| `projectName` | User-supplied project label. |
| `mode` | Captured `demo` or `api` mode. |
| `status` | Fixture presentation state or actual service state mapped from observed responses. |
| `logs` | Sample logs in Demo; only service-supplied/sanitized lines in API mode. |
| `diagnostics` | Sanitized payload, response, elapsed time, and supplied identifiers. |

No workflow state or progress percentage is invented in API mode. API operations require a locally configured, verified CGC/HamtayarDemo endpoint and dependencies.

## OperationLifecycle

Shared lifecycle for all workspaces: `idle → validating → pending → completed | failed | uncertain`. Every operation records its mode and provenance and is owned by a lightweight in-memory app-level manager, so it remains observable across workspace navigation. Mode switching is disabled while pending; once allowed, the switch clears transient operation results/history but retains metadata definitions. Logout clears drafts/results and stops local polling/observers without claiming server-side work was canceled. Stale responses cannot overwrite a newer operation. Fixture outcomes are never stored as API outcomes, and API failures never transition to fixtures. No background service or persistent job system is introduced.
