"""Format-neutral protected text ranges shared by document processors."""

import re
from collections.abc import Callable, Iterable

from packages.contracts.document import ProtectedSpan

_PROTECTED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url", re.compile(r"(?i)\b(?:https?://|ftp://|www\.)[^\s<>]+")),
    ("email", re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")),
    ("path", re.compile(r"(?<!\w)(?:[A-Za-z]:\\|\\\\|/)[^\s<>]+")),
    ("technical_expression", re.compile(r"(?<!\w)[A-Za-z_][A-Za-z0-9_]*\s*=\s*[-+]?[A-Za-z0-9_.]+")),
    ("technical_identifier", re.compile(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9_]*(?:(?:[._-])[A-Za-z0-9_]+)+(?![A-Za-z0-9])")),
)

_KIND_PRIORITY = {
    "code_payload": 0,
    "inline_code": 0,
    "link_destination": 1,
    "url": 2,
    "email": 3,
    "path": 4,
    "technical_expression": 5,
    "technical_identifier": 6,
    "list_marker": 7,
}


def find_protected_spans(text: str) -> list[ProtectedSpan]:
    """Find format-independent URLs, paths, email addresses, and identifiers."""
    spans = []
    for kind, pattern in _PROTECTED_PATTERNS:
        for match in pattern.finditer(text):
            end = match.end()
            if kind == "url":
                end = _trim_unbalanced_closers(text, match.start(), end)
            if end > match.start():
                spans.append(ProtectedSpan(start=match.start(), end=end, kind=kind))
    url_ranges = [(span.start, span.end) for span in spans if span.kind == "url"]
    spans = [
        span for span in spans
        if span.kind == "url"
        or not any(start <= span.start < end for start, end in url_ranges)
    ]
    return _merge_spans(text, spans)


def transform_with_protection(
    text: str,
    explicit_spans: Iterable[ProtectedSpan],
    transform: Callable[[str], str],
) -> tuple[str, list[ProtectedSpan]]:
    """Transform text through temporary sentinels and rebase exact ranges.

    Temporary sentinels let whitespace and other transformations see context across
    protected boundaries while keeping each payload byte-for-character unchanged.
    """
    candidates = list(explicit_spans)
    for span in candidates:
        if isinstance(span.start, bool) or isinstance(span.end, bool):
            raise TypeError("Protected span offsets must be integer code-point offsets")
        if not isinstance(span.start, int) or not isinstance(span.end, int):
            raise TypeError("Protected span offsets must be integer code-point offsets")
        if not 0 <= span.start < span.end <= len(text):
            raise ValueError("Protected span is outside the text being processed")
    candidates.extend(find_protected_spans(text))
    spans = _merge_spans(text, candidates)
    if not spans:
        return transform(text), []

    markers: list[str] = []
    marker_codepoint = 0xF0000
    for _ in spans:
        while chr(marker_codepoint) in text or chr(marker_codepoint) in markers:
            marker_codepoint += 1
        markers.append(chr(marker_codepoint))
        marker_codepoint += 1

    pieces: list[str] = []
    cursor = 0
    for span, marker in zip(spans, markers, strict=True):
        pieces.extend((text[cursor:span.start], marker))
        cursor = span.end
    pieces.append(text[cursor:])
    transformed = transform("".join(pieces))

    output: list[str] = []
    result_spans: list[ProtectedSpan] = []
    cursor = 0
    output_length = 0
    for marker, span in zip(markers, spans, strict=True):
        marker_at = transformed.find(marker, cursor)
        if marker_at < 0:
            # A processor must not silently discard a protected marker.
            raise ValueError("Text transform removed a protected-span sentinel")
        prefix = transformed[cursor:marker_at]
        output.append(prefix)
        output_length += len(prefix)
        payload = text[span.start:span.end]
        output.append(payload)
        result_spans.append(ProtectedSpan(
            start=output_length,
            end=output_length + len(payload),
            kind=span.kind,
        ))
        output_length += len(payload)
        cursor = marker_at + len(marker)
    output.append(transformed[cursor:])
    return "".join(output), result_spans


def _merge_spans(text: str, spans: Iterable[ProtectedSpan]) -> list[ProtectedSpan]:
    ordered = sorted(spans, key=lambda span: (span.start, span.end, _KIND_PRIORITY[span.kind]))
    merged: list[ProtectedSpan] = []
    for span in ordered:
        if merged and span.start < merged[-1].end:
            previous = merged[-1]
            primary_kind = min((previous.kind, span.kind), key=_KIND_PRIORITY.__getitem__)
            merged[-1] = ProtectedSpan(
                start=previous.start,
                end=max(previous.end, span.end),
                kind=primary_kind,
            )
        else:
            merged.append(span)
    return merged


def _trim_unbalanced_closers(text: str, start: int, end: int) -> int:
    """Exclude Markdown/container closers while retaining balanced URL parentheses."""
    pairs = {")": "(", "]": "[", "}": "{"}
    while end > start and text[end - 1] in pairs:
        closer = text[end - 1]
        segment = text[start:end]
        if segment.count(closer) <= segment.count(pairs[closer]):
            break
        end -= 1
    return end
