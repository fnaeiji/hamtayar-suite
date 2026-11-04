"""Clean extraction artifacts without changing source text or structural whitespace."""

import json
import re
import unicodedata
from dataclasses import asdict, dataclass

from packages.contracts.document import DocumentBlock, ParsedDocument, ProtectedSpan
from packages.documents.protection import transform_with_protection


@dataclass(frozen=True)
class CleaningConfig:
    """Options for safe cleanup of unprotected extracted text."""

    remove_control_chars: bool = True
    remove_zero_width_junk: bool = True
    normalize_whitespace: bool = True
    normalize_line_breaks: bool = True
    fix_broken_urls_and_emails: bool = False
    # Structural boundaries and meaningful whitespace are preserved by default.
    strip_block_text: bool = False


class DocumentCleaner:
    """Produce a cleaned text view while preserving extracted text and structure."""

    PROFILE = "document-cleaning-v2"

    @staticmethod
    def clean_text(
        text: str,
        config: CleaningConfig | None = None,
        *,
        protected_spans: list[ProtectedSpan] | None = None,
    ) -> str:
        """Clean an unstructured string, optionally honoring exact protected ranges."""
        options = config or CleaningConfig()
        cleaned, _ = transform_with_protection(
            text,
            protected_spans or [],
            lambda segment: DocumentCleaner._clean_segment(segment, options),
        )
        return cleaned

    @staticmethod
    def _clean_segment(text: str, options: CleaningConfig) -> str:
        if options.normalize_line_breaks:
            text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = "".join(
            " " if char.isspace() and char not in "\n\r\t" else char
            for char in text
        )
        if options.remove_zero_width_junk:
            # Keep ZWNJ, ZWJ, WORD JOINER, and variation selectors; drop known extraction marks.
            text = re.sub("[\u200b\ufeff\u200e\u200f\u202a-\u202e]", "", text)
        if options.remove_control_chars:
            text = "".join(
                char for char in text
                if char in "\n\t\u200c\u200d"
                or 0xF0000 <= ord(char) <= 0xFFFFD
                or not unicodedata.category(char).startswith("C")
            )
        if options.normalize_whitespace:
            # Collapse repeated interior spaces only; retain tabs, line starts, trailing
            # hard-break spaces, and all newlines.
            text = "\n".join(
                re.sub(r"(?<=\S) {2,}(?=\S)", " ", line)
                for line in text.split("\n")
            )
        if options.fix_broken_urls_and_emails:
            text = re.sub(r"(?<=\S)-\n(?=\S)", "", text)
        if options.strip_block_text:
            text = text.strip()
        return text

    @classmethod
    def clean_block(cls, block: DocumentBlock, config: CleaningConfig | None = None) -> DocumentBlock:
        """Return a cleaned block view; code blocks bypass cleanup exactly."""
        if block.block_type == "code":
            source = block.effective_text
            return DocumentBlock.model_validate({**block.model_dump(), "normalized_text": source})
        options = config or CleaningConfig()
        source = block.effective_text
        should_collapse = options.normalize_whitespace and block.block_type == "paragraph"
        segment_options = options if should_collapse else CleaningConfig(
            remove_control_chars=options.remove_control_chars,
            remove_zero_width_junk=options.remove_zero_width_junk,
            normalize_whitespace=False,
            normalize_line_breaks=options.normalize_line_breaks,
            fix_broken_urls_and_emails=options.fix_broken_urls_and_emails,
            strip_block_text=options.strip_block_text,
        )
        cleaned, spans = transform_with_protection(
            source,
            block.protected_spans,
            lambda segment: cls._clean_segment(segment, segment_options),
        )
        return DocumentBlock.model_validate({
            **block.model_dump(), "normalized_text": cleaned, "protected_spans": spans,
        })

    @classmethod
    def clean_document(cls, doc: ParsedDocument, config: CleaningConfig | None = None) -> ParsedDocument:
        """Clean block views and record the deterministic cleaning profile."""
        options = config or CleaningConfig()
        metadata = dict(doc.metadata)
        metadata.update({
            "processing.cleaning_profile": cls.PROFILE,
            "processing.cleaning_config": json.dumps(asdict(options), sort_keys=True, separators=(",", ":")),
        })
        return ParsedDocument.model_validate({
            **doc.model_dump(),
            "blocks": [cls.clean_block(block, options) for block in doc.blocks],
            "metadata": metadata,
        })
