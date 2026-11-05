# Specification: Unified Hamtayar Demo

**Current scope**: user-approved revision, 2026-11-05. This replaces superseded visible UI requirements from earlier revisions; the original PRD remains reference input.

## User journeys

1. Sign in with the public demo account, open a dashboard with four workspace cards, navigate, refresh the tab session, and log out.
2. Process organizational documents: select/drop PDF, DOCX, TXT or Markdown, set independent center and classification per file, preview, submit a labeled Demo operation and keep per-file outcomes.
3. Ask a question using the two selects center/access level and inspect a safe Markdown sample answer. Centers come from successful session document registrations. Access level maps to intended document-type equality; it is not a trusted authorization grant.
4. Search a literal phrase in registered session TXT/Markdown, with center and document-classification filters, and inspect real local matches/snippets. Unsupported files disclose missing local search coverage.
5. Process a codebase inside the same dashboard using the existing HamtayarDemo interface and its eight code submenus, without running a second frontend server.

## Requirements

- Persian RTL, locally bundled Vazirmatn, formal light main surfaces and consistent navy navigation. Desktop and 390px mobile actions remain accessible without page-wide horizontal overflow.
- Exactly four main workspaces: پردازش اسناد سازمانی، پرسش‌وپاسخ، جستجو عبارت در اسناد سازمانی، پردازش کدبیس. Dashboard is the overview route. Code submenus live in the main sidebar.
- Fixed demo login `demo` / `Hamtayar123!`; password is never persisted. This is not service authentication.
- Documents have one center/type form per file; no shared duplicate panel or editable metadata-settings route. Classification/access options are normal/confidential/highly_confidential, labeled عادی / محرمانه / خیلی محرمانه.
- Demo document success registers session records by source identity. Normalize center whitespace and deduplicate centers. Failed/pending/unsubmitted drafts never become registered documents.
- Local search decodes actual UTF-8 TXT/Markdown up to 2 MiB after successful Demo processing. This is a local-search memory budget, not an upload cap. Other formats/sizes have explicit unavailable reasons; do not fabricate matches.
- Literal phrase search ignores English case and combines center/classification equality with AND. Render matching text safely with React; no regex/query-language input or raw HTML execution.
- Files, text, filters, answers/history and centers remain memory-only; clear on logout, mode change and reload. Tab login may survive refresh through sessionStorage.
- Keep generation-tagged operations across main navigation, reject stale completion, block duplicate submit/mode switch while pending, and do not equate browser abort with service cancellation.
- Document/Q&A Demo is offline and clearly labeled. Keep Hamtayar API adapters gated until deployed readiness is verified; never fall back from API failure to fixtures.
- Serve the native CGC UI as a second entry of the same Vite build/server. Embedded CSS/state is isolated, and the original code application remains the single source of its processing screens.
- Parent/child code navigation accepts only known page keys from the exact same origin and expected window. Preserve selected project and unsaved settings across code submenus.
- Use `/code-api` same-origin transport with a loopback-only backend target and explicit local backend Origin allowances. No public unauthenticated proxy, backend workflow change, database mutation or auth bypass is part of this revision.
- Provide one PowerShell launcher for the existing configured Python backend plus the main frontend. State prerequisite/environment limits honestly.

## Acceptance boundaries

Unit/component and browser fixture checks prove frontend behavior and proxy wiring, not live CGC/Neo4j/provider readiness. Live ingestion/retrieval remains external. Retain active Spec Kit governance; remove obsolete runtime implementations and tests tied solely to removed behavior.
