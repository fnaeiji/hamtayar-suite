"""Query preprocessing for lexical search: reuse the document normalizer, never duplicate it.

The normalizer is **injected**, not imported: the committed architecture map
(`test/architecture/test_import_rules.py`) allows `packages/retrieval` to import only
`contracts`, `storage`, `access` and `knowledge`, so retrieval must not import
`packages.documents` directly. The composition layer (an `apps/*` caller) passes the existing
`PersianNormalizer` from `packages/documents/normalization/`; this module only drives it.

Why normalization is mandatory (verified 2026-11-03 on Qdrant 1.20.0): the full-text index does not
fold Persian/Arabic variants — an un-normalized `جستجوي` matched nothing while `جستجوی` matched; the
WORD tokenizer treats ZWNJ and space identically, while a joined form (`میتوان`) stays a different token.
"""

from __future__ import annotations

from typing import Protocol

__all__ = [
    "MAX_QUERY_LENGTH",
    "QueryNormalizer",
    "normalize_phrase",
    "normalize_query",
]

MAX_QUERY_LENGTH = 512


class QueryNormalizer(Protocol):
    """Structural type of the existing Persian normalizer (`PersianNormalizer`)."""

    def normalize_text(self, text: str) -> str: ...


def _normalize(value: str, *, field: str, normalizer: QueryNormalizer) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{field} must not be empty")
    normalized = normalizer.normalize_text(text).strip()
    if not normalized:
        raise ValueError(f"{field} must not be empty after normalization")
    if len(normalized) > MAX_QUERY_LENGTH:
        raise ValueError(f"{field} must be at most {MAX_QUERY_LENGTH} characters")
    return normalized


def normalize_query(query: str, *, normalizer: QueryNormalizer) -> str:
    """Normalize a lexical query and reject empty/oversized input.

    Raises:
        ValueError: empty after normalization, or longer than `MAX_QUERY_LENGTH` characters
            (a typed error is pending approval — task T009).
    """
    return _normalize(query, field="query", normalizer=normalizer)


def normalize_phrase(phrase: str, *, normalizer: QueryNormalizer) -> str:
    """Same normalization for phrase searches; inner spacing is preserved for the engine."""
    return _normalize(phrase, field="phrase", normalizer=normalizer)
