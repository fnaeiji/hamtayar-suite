"""Parse plain-text files into the shared document contracts."""

from pathlib import Path

from packages.contracts.common import SourceLocation, SourceVersion
from packages.contracts.document import DocumentBlock, ParsedDocument


class TxtParser:
    """Turn blank-line-separated plain text into ordered paragraph blocks."""

    @classmethod
    def parse_content(
        cls,
        content: str,
        source: SourceVersion,
        *,
        file_path: str | Path | None = None,
    ) -> ParsedDocument:
        """Parse plain-text content, retaining the original in document metadata."""
        if not isinstance(content, str):
            raise TypeError("Text content must be a string")

        path = str(file_path) if file_path is not None else None
        lines = content.splitlines()
        blocks: list[DocumentBlock] = []
        index = 0
        while index < len(lines):
            if not lines[index].strip():
                index += 1
                continue
            start = index
            while index < len(lines) and lines[index].strip():
                index += 1
            blocks.append(DocumentBlock(
                block_type="paragraph",
                text="\n".join(lines[start:index]),
                location=SourceLocation(
                    file_path=path,
                    start_line=start + 1,
                    end_line=index,
                ),
                block_id=f"block-{len(blocks) + 1:06d}",
            ))

        metadata = {
            "parser": "txt",
            "parser_implementation": "hamtayar-txt-parser",
            "parser_version": "1.1.0",
            "original_content": content,
            "original_content_semantics": "decoded UTF-8 text; file reads use universal newline conversion and this is not an exact byte copy",
        }
        if path is not None:
            metadata["source_file"] = path
        return ParsedDocument(source=source, blocks=blocks, metadata=metadata)

    @classmethod
    def parse_file(cls, path: str | Path, source: SourceVersion) -> ParsedDocument:
        """Read a UTF-8 text file and parse it into a ``ParsedDocument``."""
        file_path = Path(path)
        content = file_path.read_text(encoding="utf-8")
        return cls.parse_content(content, source, file_path=file_path)
