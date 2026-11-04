"""Parse Markdown with markdown-it-py into shared, format-neutral document blocks."""

import re
from importlib.metadata import version
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

from packages.contracts.common import SourceLocation, SourceVersion
from packages.contracts.document import DocumentBlock, ParsedDocument, ProtectedSpan


class MarkdownParser:
    """Parse Markdown structure while retaining source-derived text and locations."""

    PROFILE = "markdown-it-py"

    @classmethod
    def parse_content(
        cls,
        content: str,
        source: SourceVersion,
        *,
        file_path: str | Path | None = None,
    ) -> ParsedDocument:
        """Parse Markdown content and preserve its decoded original in metadata."""
        if not isinstance(content, str):
            raise TypeError("Markdown content must be a string")
        path = str(file_path) if file_path is not None else None
        parse_content = content.removeprefix("\ufeff")
        lines = parse_content.splitlines()
        tokens = MarkdownIt("commonmark").enable("table").parse(parse_content)
        blocks: list[DocumentBlock] = []
        index = 0

        def add(
            block_type: str,
            start: int,
            end: int,
            text: str,
            *,
            heading_level: int | None = None,
            code_language: str | None = None,
            spans: list[ProtectedSpan] | None = None,
        ) -> None:
            ordinal = len(blocks) + 1
            blocks.append(DocumentBlock(
                block_type=block_type,
                text=text,
                location=SourceLocation(file_path=path, start_line=start + 1, end_line=max(start + 1, end)),
                block_id=f"block-{ordinal:06d}",
                heading_level=heading_level,
                code_language=code_language,
                protected_spans=spans or [],
            ))

        while index < len(tokens):
            token = tokens[index]
            if token.type in {"heading_open", "paragraph_open"}:
                inline = tokens[index + 1]
                assert inline.type == "inline" and token.map is not None
                start, end = token.map
                block_type = "heading" if token.type == "heading_open" else "paragraph"
                text = inline.content if block_type == "heading" else "\n".join(lines[start:end])
                spans = cls._inline_code_spans(text, inline)
                add(
                    block_type,
                    start,
                    end,
                    text,
                    heading_level=int(token.tag[1:]) if block_type == "heading" else None,
                    spans=spans,
                )
                index += 3
                continue

            if token.type in {"bullet_list_open", "ordered_list_open", "blockquote_open"}:
                start = token.map[0] if token.map else 0
                depth = 1
                end_index = index + 1
                while end_index < len(tokens) and depth:
                    nested = tokens[end_index]
                    if nested.type in {"bullet_list_open", "ordered_list_open", "blockquote_open"}:
                        depth += 1
                    elif nested.type in {"bullet_list_close", "ordered_list_close", "blockquote_close"}:
                        depth -= 1
                    end_index += 1
                end = token.map[1] if token.map else start + 1
                # Markdown-it may include the blank separator after a list/quote
                # in its source map. Separator lines belong to no block range.
                while end > start and not lines[end - 1].strip():
                    end -= 1
                block_type = "quote" if token.type == "blockquote_open" else "list"
                text = "\n".join(lines[start:end])
                if block_type == "list" and end > start and (
                    end < len(lines) or parse_content.endswith(("\n", "\r"))
                ):
                    text += "\n"
                spans = cls._nested_inline_spans(text, tokens[index:end_index])
                if block_type == "list":
                    spans.extend(cls._list_marker_spans(text))
                add(block_type, start, end, text, spans=spans)
                index = end_index
                continue

            if token.type == "table_open":
                start, end = token.map or [0, 0]
                text = "\n".join(lines[start:end])
                end_index = index
                while end_index < len(tokens) and tokens[end_index].type != "table_close":
                    end_index += 1
                add("table", start, end, text, spans=cls._nested_inline_spans(text, tokens[index:end_index + 1]))
                index = end_index + 1
                continue

            if token.type in {"fence", "code_block"}:
                start, end = token.map or [0, 0]
                language = token.info.strip().split(maxsplit=1)[0] if token.type == "fence" and token.info.strip() else None
                text = token.content if token.type == "fence" else "\n".join(lines[start:end])
                add("code", start, end, text, code_language=language)
                index += 1
                continue

            if token.type == "hr":
                start, end = token.map or [0, 0]
                add("paragraph", start, end, "\n".join(lines[start:end]))
                index += 1
                continue
            index += 1

        metadata = {
            "parser": "markdown",
            "parser_implementation": cls.PROFILE,
            "parser_version": version("markdown-it-py"),
            "original_content": content,
            "original_content_semantics": "decoded UTF-8 text; file reads use universal newline conversion and this is not an exact byte copy",
        }
        if path is not None:
            metadata["source_file"] = path
        return ParsedDocument(source=source, blocks=blocks, metadata=metadata)

    @staticmethod
    def _inline_code_spans(text: str, inline: Token) -> list[ProtectedSpan]:
        if not inline.children:
            return []
        spans: list[ProtectedSpan] = []
        cursor = 0
        for child in inline.children:
            if child.type != "code_inline" or not child.markup:
                continue
            # Inline token content omits Markdown delimiters and list/quote prefixes.
            # Locate the delimiters in the source-derived block text itself.
            start = text.find(child.markup, cursor)
            closing = text.find(child.markup, start + len(child.markup)) if start >= 0 else -1
            if start >= 0 and closing >= 0:
                end = closing + len(child.markup)
                spans.append(ProtectedSpan(start=start, end=end, kind="inline_code"))
                cursor = end
        return spans

    @classmethod
    def _nested_inline_spans(cls, text: str, tokens: list[Token]) -> list[ProtectedSpan]:
        return [
            span
            for token in tokens
            if token.type == "inline"
            for span in cls._inline_code_spans(text, token)
        ]

    @staticmethod
    def _list_marker_spans(text: str) -> list[ProtectedSpan]:
        """Protect syntax markers and indentation so normalization keeps nesting."""
        spans: list[ProtectedSpan] = []
        offset = 0
        for line in text.split("\n"):
            match = re.match(r"[ \t]*(?:[-+*]|\d+[.)])[ \t]+", line)
            if match:
                spans.append(ProtectedSpan(start=offset, end=offset + match.end(), kind="list_marker"))
            offset += len(line) + 1
        return spans

    @classmethod
    def parse_file(cls, path: str | Path, source: SourceVersion) -> ParsedDocument:
        """Read a UTF-8 Markdown file and parse it."""
        file_path = Path(path)
        content = file_path.read_text(encoding="utf-8")
        return cls.parse_content(content, source, file_path=file_path)
