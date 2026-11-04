"""Local, synchronous-from-CLI entry point to the shared Document Ingestion executor.

Run: uv run python -m apps.document_ingestion.cli /path/to/document.pdf
The default bootstrap registry has no fake executor: real processing requires
registration of the real Graph executor in apps.orchestration.execution.
"""

import argparse
import asyncio
import hashlib
import json
import re
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from apps.bootstrap import BootstrapRegistry, bootstrap
from apps.core.config import Settings, get_settings
from apps.document_ingestion.api.schemas.jobs import DocumentExecutionRequest
from apps.orchestration.execution import (
    DocumentExecutionFailed,
    DocumentExecutionTimedOut,
    ExecutorUnavailable,
    get_runtime_registry,
    resolve_document_ingestion_executor,
    run_document_ingestion,
)
from packages.contracts.common import ContentRef, SourceRef, SourceVersion
from packages.contracts.document import DocumentInput

# Explicit exit codes (0 success; any non-zero is failure).
EXIT_OK = 0
EXIT_INVALID_FILE = 2
EXIT_NOT_CONFIGURED = 3
EXIT_PROCESSING_FAILED = 4
EXIT_TIMEOUT = 5

# Match the currently supported Task-04 upload types. Import neither FastAPI
# nor the HTTP router here; the CLI is a separate transport adapter.
CONTENT_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PROFILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CHUNK_SIZE = 256 * 1024


class InvalidLocalFile(ValueError):
    """Input file or user-supplied metadata is invalid."""


def _validate_content(path: Path, suffix: str) -> None:
    """Basic signature/UTF-8 checks; final parsing must still be untrusted."""
    if suffix == ".pdf":
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise InvalidLocalFile("Invalid PDF header")
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(archive.namelist()):
                    raise InvalidLocalFile("Invalid DOCX structure")
        except (zipfile.BadZipFile, OSError, ValueError) as exc:
            raise InvalidLocalFile("Invalid DOCX file") from exc
    else:
        import codecs

        decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(_CHUNK_SIZE), b""):
                    if b"\x00" in chunk:
                        raise InvalidLocalFile("Text file contains binary data")
                    decoder.decode(chunk)
                decoder.decode(b"", final=True)
        except UnicodeDecodeError as exc:
            raise InvalidLocalFile("Text file is not UTF-8") from exc


def build_local_request(
    path: Path,
    *,
    max_upload_size_bytes: int,
    source_id: str | None,
    knowledge_space_id: str,
    version: str,
    processing_profile: str,
) -> DocumentExecutionRequest:
    """Convert a trusted CLI file path to Task-04's exact Graph input type."""
    try:
        full_path = path.expanduser().resolve(strict=True)
        if not full_path.is_file():
            raise InvalidLocalFile("Input path is not a regular file")
        size = full_path.stat().st_size
    except (OSError, RuntimeError) as exc:
        raise InvalidLocalFile("Input file is unavailable") from exc

    if size == 0:
        raise InvalidLocalFile("Input file is empty")
    if size > max_upload_size_bytes:
        raise InvalidLocalFile("Input file exceeds the configured size limit")
    suffix = full_path.suffix.lower()
    if suffix not in CONTENT_TYPES:
        raise InvalidLocalFile("Unsupported file format")

    # Path-derived default is deterministic on the same machine. Callers can
    # override it to match the source_id used by HTTP ingestion.
    source_id = source_id or "local-" + hashlib.sha256(
        str(full_path).encode("utf-8")
    ).hexdigest()[:16]
    for label, value in (
        ("source_id", source_id),
        ("knowledge_space_id", knowledge_space_id),
        ("version", version),
    ):
        if _IDENTIFIER.fullmatch(value) is None:
            raise InvalidLocalFile(f"Invalid {label}")
    if _PROFILE.fullmatch(processing_profile) is None:
        raise InvalidLocalFile("Invalid processing_profile")

    try:
        _validate_content(full_path, suffix)
    except OSError as exc:
        raise InvalidLocalFile("Unable to read input file") from exc

    source = SourceVersion(
        source=SourceRef(
            source_id=source_id,
            knowledge_space_id=knowledge_space_id,
            source_type="document",
        ),
        version=version,
    )
    return DocumentExecutionRequest(
        document=DocumentInput(source=source, content=ContentRef(uri=full_path.as_uri())),
        filename=full_path.name,
        content_type=CONTENT_TYPES[suffix],
        size_bytes=size,
        processing_profile=processing_profile,
    )


async def ingest_local_document(
    request: DocumentExecutionRequest,
    *,
    settings: Settings,
    registry: BootstrapRegistry,
):
    """Use the very same Bootstrap service key/Executor as the Task-04 HTTP API."""
    async with bootstrap(settings, registry) as container:
        executor = resolve_document_ingestion_executor(container)
        return await run_document_ingestion(
            executor,
            request,
            timeout_seconds=container.settings.request_timeout_seconds,
        )


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingest-document",
        description="Execute Document Ingestion directly for a local file (no Queue/Worker).",
    )
    parser.add_argument("file", type=Path, help="Path to an existing PDF/DOCX/TXT/MD file")
    parser.add_argument("--source-id", help="Source identity; default is derived from resolved file path")
    parser.add_argument("--knowledge-space-id", default="local", help="Knowledge space (default: local)")
    parser.add_argument("--version", default="v1", help="Document version (default: v1)")
    parser.add_argument("--processing-profile", default="default", help="Processing profile")
    return parser


def _print_failure(code: str, message: str, request_id: str) -> None:
    print(
        json.dumps({"status": "failed", "error": {"code": code, "message": message},
                    "request_id": request_id}, ensure_ascii=False),
        file=sys.stderr,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    registry: BootstrapRegistry | None = None,
) -> int:
    """CLI entry point. Dependencies injected in tests, never faked in production."""
    args = make_parser().parse_args(argv)
    request_id = str(uuid4())
    try:
        current_settings = settings if settings is not None else get_settings()
        execution_request = build_local_request(
            args.file,
            max_upload_size_bytes=current_settings.max_upload_size_bytes,
            source_id=args.source_id,
            knowledge_space_id=args.knowledge_space_id,
            version=args.version,
            processing_profile=args.processing_profile,
        )
    except (InvalidLocalFile, ValueError) as exc:
        _print_failure("invalid_input", str(exc), request_id)
        return EXIT_INVALID_FILE
    except Exception:
        _print_failure("configuration_error", "Unable to load configuration", request_id)
        return EXIT_PROCESSING_FAILED

    try:
        effective_registry = registry if registry is not None else get_runtime_registry()
        result = asyncio.run(
            ingest_local_document(
                execution_request, settings=current_settings, registry=effective_registry
            )
        )
    except ExecutorUnavailable:
        _print_failure("executor_unavailable", "Document ingestion executor is not configured", request_id)
        return EXIT_NOT_CONFIGURED
    except DocumentExecutionTimedOut:
        _print_failure("processing_timeout", "Document processing timed out", request_id)
        return EXIT_TIMEOUT
    except DocumentExecutionFailed:
        _print_failure("processing_failed", "Document processing failed", request_id)
        return EXIT_PROCESSING_FAILED
    except Exception:
        # Includes dependency initialization errors; keep client-visible
        # diagnostics stable without printing secrets or stack traces.
        _print_failure("processing_failed", "Document processing failed", request_id)
        return EXIT_PROCESSING_FAILED

    print(json.dumps({
        "status": "completed",
        "source_id": execution_request.document.source.source.source_id,
        "version": execution_request.document.source.version,
        "chunks_indexed": result.chunks_indexed,
        "request_id": request_id,
    }, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
