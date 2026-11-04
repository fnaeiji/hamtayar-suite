"""Conservative Persian normalization with Hazm and exact protected spans."""

import importlib.metadata
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Literal

from hazm import Normalizer as HazmNormalizer

from packages.contracts.document import DocumentBlock, ParsedDocument, ProtectedSpan
from packages.documents.protection import transform_with_protection


@dataclass(frozen=True)
class PersianNormalizationConfig:
    """Independent, deterministic controls for Persian text normalization."""

    enabled: bool = True
    normalize_unicode_nfc: bool = True
    unify_arabic_chars: bool = True
    remove_diacritics: bool = True
    remove_tatweel: bool = True
    normalize_zwnj: bool = True
    apply_affix_spacing: bool = True
    correct_spacing: bool = False
    correct_verb_prefixes: bool = False
    reduce_repeated_characters: bool = False
    persian_style: bool = False
    digit_policy: Literal["preserve", "fa", "en"] = "preserve"
    preserve_protected_content: bool = True
    normalize_punctuation: bool = False


@lru_cache(maxsize=64)
def _hazm_normalizer(
    correct_spacing: bool,
    remove_diacritics: bool,
    reduce_repeated_characters: bool,
    persian_style: bool,
    correct_verb_prefixes: bool,
) -> HazmNormalizer:
    """Cache Hazm instances by their explicit behavior settings."""
    return HazmNormalizer(
        correct_spacing=correct_spacing,
        remove_diacritics=remove_diacritics,
        remove_specials_chars=False,
        decrease_repeated_chars=reduce_repeated_characters,
        persian_style=persian_style,
        persian_numbers=False,
        unicodes_replacement=False,
        seperate_mi=correct_verb_prefixes,
    )


class PersianNormalizer:
    """Normalize prose while leaving code, URLs, paths, and identifiers intact."""

    PROFILE = "persian-hazm-normalization-v2"

    @staticmethod
    def hazm_version() -> str:
        """Return the installed Hazm distribution version."""
        return importlib.metadata.version("hazm")

    @classmethod
    def normalize_text(
        cls,
        text: str,
        config: PersianNormalizationConfig | None = None,
        *,
        protected_spans: list[ProtectedSpan] | None = None,
    ) -> str:
        """Normalize a string; disabled configuration is an exact bypass."""
        options = config or PersianNormalizationConfig()
        if not options.enabled or not text:
            return text
        if not options.preserve_protected_content:
            return cls._normalize_segment(text, options)
        normalized, _ = transform_with_protection(
            text,
            protected_spans or [],
            lambda segment: cls._normalize_segment(segment, options),
        )
        return normalized

    @staticmethod
    def _normalize_segment(text: str, options: PersianNormalizationConfig) -> str:
        if options.normalize_unicode_nfc:
            text = unicodedata.normalize("NFC", text)
        if options.unify_arabic_chars:
            text = text.translate(str.maketrans({
                "\u064a": "\u06cc", "\u0649": "\u06cc", "\u0643": "\u06a9",
                "\u06a4": "\u06a9", "\u06aa": "\u06a9", "\u06d2": "\u06cc",
            }))
        hazm = _hazm_normalizer(
            options.correct_spacing,
            options.remove_diacritics,
            options.reduce_repeated_characters,
            options.persian_style,
            options.correct_verb_prefixes,
        )
        text = hazm.normalize(text)
        if options.remove_tatweel:
            text = text.replace("\u0640", "")
        if options.normalize_zwnj:
            text = re.sub("\u200c{2,}", "\u200c", text)
            text = re.sub(r"^\u200c+|\u200c+$", "", text)
        if options.apply_affix_spacing:
            text = re.sub(
                r"(?<![\w\u200c])(\u0646?\u0645\u06cc)\s+(?=[\u0600-\u06ff])",
                lambda match: match.group(1) + "\u200c",
                text,
            )
            suffix = r"(?:\u0647\u0627(?:\u06cc)?|\u062a\u0631|\u062a\u0631\u06cc\u0646)"
            text = re.sub(
                r"(?<=[\u0600-\u06ff])\s+(" + suffix + r")(?![\u0600-\u06ff])",
                lambda match: "\u200c" + match.group(1),
                text,
            )
            plural = r"\u0647\u0627(?:\u06cc)?"
            text = re.sub(
                r"(?<=[\u0600-\u06ff])(" + plural + r")(?![\u0600-\u06ff])",
                lambda match: "\u200c" + match.group(1),
                text,
            )
        if options.digit_policy != "preserve":
            target_zero = "\u06f0" if options.digit_policy == "fa" else "0"
            def convert(match: re.Match[str]) -> str:
                value = ord(match.group())
                if 0x0660 <= value <= 0x0669:
                    digit = value - 0x0660
                elif 0x06F0 <= value <= 0x06F9:
                    digit = value - 0x06F0
                else:
                    digit = value - ord("0")
                return chr(ord(target_zero) + digit)
            text = re.sub(r"[0-9\u0660-\u0669\u06f0-\u06f9]", convert, text)
        if options.normalize_punctuation:
            text = re.sub(r"(?<=[\u0600-\u06ff]),", "\u060c", text)
            text = re.sub(r"(?<=[\u0600-\u06ff]);", "\u061b", text)
            text = re.sub(r"(?<=[\u0600-\u06ff])\?", "\u061f", text)
        return text

    @classmethod
    def normalize_block(
        cls,
        block: DocumentBlock,
        config: PersianNormalizationConfig | None = None,
    ) -> DocumentBlock:
        """Return the normalized view, preserving code blocks exactly."""
        options = config or PersianNormalizationConfig()
        source = block.effective_text
        if block.block_type == "code" or not options.enabled:
            return DocumentBlock.model_validate({**block.model_dump(), "normalized_text": source})
        normalized, spans = transform_with_protection(
            source,
            block.protected_spans,
            lambda segment: cls._normalize_segment(segment, options),
        )
        return DocumentBlock.model_validate({
            **block.model_dump(), "normalized_text": normalized, "protected_spans": spans,
        })

    @classmethod
    def normalize_document(
        cls,
        doc: ParsedDocument,
        config: PersianNormalizationConfig | None = None,
    ) -> ParsedDocument:
        """Normalize block views and record reproducible processing provenance."""
        options = config or PersianNormalizationConfig()
        metadata = dict(doc.metadata)
        metadata.update({
            "processing.normalization_profile": cls.PROFILE,
            "processing.normalization_config": json.dumps(asdict(options), sort_keys=True, separators=(",", ":")),
            "processing.hazm_version": cls.hazm_version(),
        })
        return ParsedDocument.model_validate({
            **doc.model_dump(),
            "blocks": [cls.normalize_block(block, options) for block in doc.blocks],
            "metadata": metadata,
        })
