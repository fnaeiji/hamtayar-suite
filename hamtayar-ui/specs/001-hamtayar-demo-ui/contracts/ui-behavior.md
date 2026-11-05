# Current UI behavior contract

- Main route inventory: overview `/`, documents `/documents`, Q&A `/qa`, phrase search `/search`, code `/codebase/:view`.
- Code page keys: dashboard/upload/source/search/graph/context/query/settings. `/codebase` redirects to dashboard. Old metadata-settings bookmarks redirect to overview.
- Parent code host loads `/code/index.html?embedded=1` from the same origin. Messages: `hamtayar:code:navigate`, `hamtayar:code:ready`, `hamtayar:code:page`. Page payload is restricted to the known keys; origin and exact window identity are checked.
- Frame stays mounted between code submenus, but unmounts when leaving the code route or logging out. Browser cleanup is not backend cancellation.
- Document fields are center and classification once per file. Successful Demo adds a catalog record; failures do not. Local text search includes only supported bounded UTF-8 text.
- Q&A has center and access-level controls. Phrase search has phrase, center and classification controls. Both disclose Demo/actual-service boundaries.
- Same-session navigation preserves main workspace state. Logout and permitted mode changes clear transient state; switching mode is blocked during a managed pending operation.
