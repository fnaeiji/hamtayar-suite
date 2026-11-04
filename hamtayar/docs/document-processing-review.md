# Document Processing Pipeline Review

## Pipeline and review result

## What was already correct

- The shared source wrapper already carried source namespace, source ID, and version; those fields remain untouched.
- Markdown-it already recognized fenced and indented code as code blocks, retained heading levels, and provided source line maps. TXT already treated Markdown-looking syntax and tab-separated lines as plain text.
- Source locations were kept separate from transformed text, and the sample export already recorded parser/cleaning/normalization profiles and Hazm version.
- Processing already retained the extracted `text` field and had a deterministic sample export path. The fixes below clarify and validate these existing behaviors rather than adding a parallel document schema.

The tested flow is **file → format parser → `ParsedDocument` → cleaner → Hazm-backed normalizer → processed `ParsedDocument`**. Both sample files now use this flow, with extracted text retained in `DocumentBlock.text` and the derived processing view in `DocumentBlock.normalized_text`.

## Root causes and fixes

| Observed issue | Cause | Fix |
|---|---|---|
| Fenced code appeared as a paragraph | The old Markdown parser used regular expressions, and the shared block type did not include code. | Parse Markdown tokens with `markdown-it-py`; use a shared `code` block type and retain the fence language. `text` is the code payload; the complete Markdown source remains in `original_content`. |
| Code indentation and repeated spaces changed | The cleaner stripped every block and collapsed all repeated spaces. | Code blocks bypass cleanup and normalization. Other block cleanup preserves tabs, line boundaries, indentation, and trailing hard-break spaces. |
| `print("ك  123")` lost a space | Generic whitespace cleanup ran inside code. | Code payload is protected as a complete block and tested byte-for-character at the decoded text level. |
| Emoji `👩‍💻` lost its joiner | The cleaner removed every Unicode `C*` character, including format characters with meaning. | Remove only known extraction junk; preserve ZWJ, ZWNJ, and other non-target characters. NUL and BOM are still cleaned from the processed view. |
| `v1.2.3` changed to Persian digits | Persian digit conversion defaulted to `fa`, and the version was not recognized as technical text. | Default digit policy is `preserve`. Generic URLs, paths, email addresses, assignments, and technical identifiers receive protected spans; explicit `fa`/`en` conversion skips those spans. |
| Nested list indentation changed | Lists were represented as prose and their marker/indentation whitespace was collapsed. | Markdown parser emits a shared `list` block, preserves the source Markdown text, and marks list syntax/indentation as protected. |
| Markdown hard-break spaces disappeared | Cleaner stripped trailing whitespace and the parser did not retain exact paragraph source lines. | Paragraph text comes from the original source lines, and trailing spaces before line breaks remain in the processed view. |
| Exported range pointed at `v1.2.3` in `normalized_text` but `versio` in `text` | Protected spans were rebased during processing, but the contract only said “current view”; the sample range was `[336,342)` and the exported text fields had different content at that range. | Contract now explicitly makes processed ranges address `normalized_text`; every processed block receives that field. Transformations validate and rebuild ranges after every length change. |
| Protected kinds became repeated compound strings and the URL range included `)` | Overlapping generic recognizers concatenated kind names; path matching overlapped URLs and expanded their ranges. | A fixed primary-kind precedence deduplicates overlaps. URL recognition excludes unmatched outer closers while retaining balanced parentheses. A URL span now matches the destination only. |
| Inline code changed under enabled spacing/style options | Inline-code span discovery searched rendered token content, which omits delimiters and structural prefixes, rather than the source-derived block. | The structured Markdown token still identifies code spans; the parser locates their delimiters in the original block text, and regression tests exercise enabled transformations. |
| List locations included the following blank separator | Markdown token maps may include the separator line after a list or quote. | Trailing separator lines are excluded from source ranges. Line locations are one-based and inclusive; code locations may still include fences. |
| Markdown sample’s first heading was missed | The fixture begins with a UTF-8 BOM. | Markdown parsing ignores a leading BOM for token recognition while retaining it in original-content metadata. |
| TXT Markdown-looking text/tabs risked structural interpretation | TXT parsing must remain plain text and format-neutral. | TXT parser emits paragraphs split only at blank lines. It leaves `#`, `**`, and tabs as plain text; it does not infer tables. |

## Contract changes and compatibility

`packages/contracts/document.py` adds optional `block_id`, `heading_level`, `code_language`, and `protected_spans` fields, plus shared `code`, `list`, and `quote` block types. `ProtectedSpan.kind` is now a closed vocabulary and offsets are strict integers (booleans rejected). `DocumentBlock` validates ranges as sorted, non-overlapping, and within the addressed text. `ParsedDocument` rejects duplicate non-null block IDs within one document. This tightens compatibility for clients that previously supplied arbitrary protection-kind strings or duplicate IDs; update those values to a documented kind and unique local ID.

The existing `source` wrapper and document metadata remain intact. The change is additive for existing Python callers, but serialized blocks now include optional fields and accept additional block type values; strict downstream schema consumers should be updated to the new contract version.

Text and location semantics are explicit:

- `text` retains parser-extracted source text and is not overwritten by cleaning or normalization.
- `normalized_text` is the processed text. The processing boundary always populates it, including `""` and exact-bypass code blocks. `DocumentBlock.effective_text` selects it whenever it is not `None`; only an absent value falls back to `text` for unprocessed documents.
- `protected_spans` refer to `normalized_text` in processed output (or to `text` before processing). Coordinates are zero-based Python Unicode code-point offsets with end-exclusive `[start, end)` bounds. They are not citation offsets. Invalid/stale ranges fail validation and are never clipped or dropped. Overlaps are deliberately merged using the fixed precedence: code/inline code, link destination, URL, email, path, technical expression, technical identifier, list marker.
- `location` uses one-based lines with an inclusive `end_line` and points to the original decoded source. Trailing blank separator lines belong to no block; code-block ranges may include opening/closing fences even though `text` contains only code payload. Page, sheet, and cell information remain optional.
- IDs such as `block-000001` are local. Identity combines source namespace (`knowledge_space_id`), `source_id`, source `version`, and `block_id`. Parsing is deterministic for a fixed parser/configuration/source version; sequential IDs are not promised stable across revisions.
- Processed empty blocks remain present with identity/location/metadata for traceability. A future chunker should skip an empty `effective_text`, without falling back to the extracted `text`.

`original_content` contains decoded text; filesystem reads use universal newline conversion, so it is not an exact copy of the source file bytes.

## Selected processing configuration and versions

- Python: 3.12.15; Pydantic: 2.14.2.
- Markdown parser: `markdown-it-py` 3.0.0; TXT parser profile: Hamtayar TXT parser 1.1.0.
- Persian normalization uses Hazm 0.12.1. The actual Hazm version is recorded in `processing.hazm_version`.
- Cleaning defaults remove controls and known zero-width extraction junk, normalize line endings and interior prose whitespace, and preserve block edges and structural whitespace (`strip_block_text=false`).
- Normalization defaults enable Unicode NFC, Arabic/Persian letter unification, diacritic removal, ZWNJ cleanup, and affix spacing. Digit policy is `preserve`; general spacing correction, Persian style conversion, repeated-character reduction, verb-prefix rewriting, and punctuation style changes are off. The full deterministic configuration is serialized in document metadata.
- Processing provenance uses `processing.cleaning_profile`, `processing.cleaning_config`, `processing.normalization_profile`, `processing.normalization_config`, and `processing.hazm_version`; these namespaced additions do not overwrite caller metadata.

## Representative before/after

| Before | Processed view |
|---|---|
| `print("ك  123")` in a fenced block | Exact code payload and indentation retained; language is `python`. |
| `👩‍💻` | `👩‍💻` (ZWJ retained). |
| Persian prose `نسخه 42` with default settings | `نسخه 42`; explicit `digit_policy="fa"` gives `نسخه ۴۲`. |
| `نسخه v1.2.3` with `digit_policy="fa"` | `نسخه v1.2.3`; the version identifier remains protected. |
| `می شود` / `کتاب ها` | `می‌شود` / `کتاب‌ها`. |
| Markdown hard break `first line··\nsecond line` | The two source spaces and line boundary remain in the processed block. |

## Files changed

- `packages/contracts/document.py`: shared block types, structure fields, and protected-range validation.
- `packages/ingestion/markdown/parser.py`: token-based Markdown parsing, code/list/quote blocks, heading levels, inline-code spans, and source provenance.
- `packages/ingestion/txt/parser.py`: plain-text paragraphs, locations, IDs, and parser provenance.
- `packages/documents/protection.py`: format-neutral span discovery, exact masking, and range rebasing.
- `packages/documents/cleaning/service.py` and `packages/documents/normalization/service.py`: structure-aware cleaning and configurable Hazm normalization.
- `pyproject.toml` and `uv.lock`: explicit `markdown-it-py` and Hazm runtime dependencies.
- `test/unit`, `test/contracts`, and `test/integration`: regression, contract, and end-to-end coverage using the actual implementations.
- `scripts/export_document_samples.py`: reproducible JSON export command.
- Review artifacts: `test/outputs/documents/sample_markdown_processed.json` and `test/outputs/documents/sample_txt_processed.json`.

## Commands and test results

```powershell
.venv\Scripts\python.exe scripts/export_document_samples.py
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check packages/contracts/document.py packages/contracts/common.py packages/documents/protection.py packages/documents/cleaning packages/ingestion/markdown packages/documents/normalization packages/ingestion/txt test/contracts/test_documents.py test/unit/test_document_processing_regressions.py test/unit/test_persian_normalizer.py scripts/export_document_samples.py
git diff --check
```

Final pytest result: **284 passed, 0 failed, 0 skipped**. This includes all unit, contract, architecture, and Markdown/TXT integration tests. No skip markers were reported. Targeted Ruff check passes. Environment: Python 3.12.15, Pydantic 2.14.2, pytest 8.4.2, markdown-it-py 3.0.0, Hazm 0.12.1. No checks were skipped.

## Remaining limitations

- Markdown table cells remain lossless Markdown text in a `table` block because the shared contract has no row/cell model.
- Lists and quotations preserve their original Markdown syntax in shared `list` and `quote` blocks; no renderer-specific AST is exposed to downstream packages.
- Markdown extensions beyond CommonMark plus tables are not enabled. DOCX, XLSX, PDF, chunking, and embedding remain out of scope.
- Protected technical identifiers use conservative generic patterns; domain-specific identifiers may need explicit parser-provided spans in future formats.
