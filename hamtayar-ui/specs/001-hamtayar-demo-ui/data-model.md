# Current data model

| Model | Fields / ownership |
| --- | --- |
| Document draft | Stable draft/source IDs, in-memory File, knowledge-space/version/profile, independent center/classification |
| Local document | Source ID, filename, normalized center, classification, optional UTF-8 text or a reason local search is unavailable |
| Document catalog | Session-only successful records; replace by source ID, derive unique centers |
| Metadata profile | Fixed center text and document classification select; prompt uses center/access-level selects |
| Classification | normal → عادی; confidential → محرمانه; highly_confidential → خیلی محرمانه |
| Question model | Trimmed question, descriptive user values, structured AND/equality filters; backend accepts question only |
| Phrase result | Registered document and before/match/after text slices, rendered as text |
| Operation record | ID/generation, captured mode, status, provenance, time, validated result/sanitized diagnostic |
| Code page | One of dashboard/upload/source/search/graph/context/query/settings; parent/child messages carry only this key |

No document text, credentials, answer history or code settings are stored in the main UI's localStorage. Old metadata configuration is not consumed or wiped. Real code settings remain owned by the existing backend and its `.env`.
