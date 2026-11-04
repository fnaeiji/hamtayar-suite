"""Synchronous HTTP document ingestion. Await Graph result; no queue is used."""

import asyncio
import codecs
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, BinaryIO

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from apps.bootstrap import AppContainer, get_container
from apps.core.exceptions import ApplicationError
from apps.orchestration.execution import (
    DocumentExecutionFailed,
    DocumentExecutionTimedOut,
    run_document_ingestion,
)
from apps.document_ingestion.api.dependencies import (
    DocumentIngestionExecutor,
    get_document_ingestion_executor,
)
from apps.document_ingestion.api.schemas.jobs import (
    DocumentExecutionRequest,
    DocumentExecutionResult,
    DocumentUploadRequest,
    DocumentUploadResponse,
)
from packages.contracts.common import ContentRef, SourceRef, SourceVersion
from packages.contracts.document import DocumentInput
from packages.contracts.errors import ErrorCode

router = APIRouter(prefix="/api/v1/document-ingestion", tags=["document-ingestion"])

# A deliberately narrow MVP allowlist; add formats only with parser support.
_ALLOWED_MIMES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}
_CHUNK_SIZE = 256 * 1024


@dataclass(frozen=True)
class _StagedFile:
    work_dir: Path
    path: Path
    size_bytes: int


def _invalid(message: str, status_code: int = 422) -> ApplicationError:
    return ApplicationError(
        code=ErrorCode.VALIDATION_ERROR,
        message=message,
        status_code=status_code,
    )


def _validate_upload_metadata(upload: UploadFile) -> tuple[str, str]:
    filename = upload.filename or ""
    if (
        not filename
        or len(filename) > 255
        or any(c in filename for c in ("/", "\\", "\x00", "\r", "\n"))
        or filename in {".", ".."}
    ):
        raise _invalid("Invalid document filename")

    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_MIMES:
        raise _invalid("Unsupported document format", 415)

    content_type = (upload.content_type or "").lower().split(";", 1)[0].strip()
    if content_type not in _ALLOWED_MIMES[suffix]:
        raise _invalid("File content type does not match the extension", 415)
    return filename, content_type


def _validate_file_signature(path: Path, suffix: str) -> None:
    """Cheap format checks; a future parser must still treat files as untrusted."""
    if suffix == ".pdf":
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise _invalid("Invalid PDF file")
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                    raise _invalid("Invalid DOCX file")
        except (zipfile.BadZipFile, OSError, ValueError) as exc:
            raise _invalid("Invalid DOCX file") from exc
    else:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        try:
            with path.open("rb") as stream:
                for data in iter(lambda: stream.read(_CHUNK_SIZE), b""):
                    if b"\x00" in data:
                        raise _invalid("Invalid text document")
                    decoder.decode(data)
                decoder.decode(b"", final=True)
        except UnicodeDecodeError as exc:
            raise _invalid("Text files must use UTF-8") from exc


def _stage_upload(fileobj: BinaryIO, root_dir: Path, max_bytes: int, suffix: str) -> _StagedFile:
    """Run blocking file operations in a worker thread, not the event loop."""
    root_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="hamtayar-ingest-", dir=root_dir))
    path = work_dir / "payload"  # Never use the untrusted original filename.
    total = 0
    try:
        with path.open("xb") as output:
            while True:
                chunk = fileobj.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise _invalid("Document exceeds the upload size limit", 413)
                output.write(chunk)
        if total == 0:
            raise _invalid("Uploaded document is empty")
        _validate_file_signature(path, suffix)
        return _StagedFile(work_dir=work_dir, path=path, size_bytes=total)
    except BaseException:
        shutil.rmtree(work_dir)
        raise


@router.post("/jobs", response_model=DocumentUploadResponse, status_code=200)
async def upload_and_process_document(
    request: Request,
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT or Markdown document")],
    source_id: Annotated[str, Form(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")],
    knowledge_space_id: Annotated[str, Form(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")],
    version: Annotated[str, Form(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")],
    container: Annotated[AppContainer, Depends(get_container)],
    executor: Annotated[DocumentIngestionExecutor, Depends(get_document_ingestion_executor)],
    processing_profile: Annotated[str, Form(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")] = "default",
) -> DocumentUploadResponse:
    """Stage an uploaded file, await ingestion result, then always remove it."""
    # Form validation is handled by FastAPI; keep schema as an explicit API contract.
    metadata = DocumentUploadRequest(
        source_id=source_id,
        knowledge_space_id=knowledge_space_id,
        version=version,
        processing_profile=processing_profile,
    )
    filename, content_type = _validate_upload_metadata(file)
    max_bytes = container.settings.max_upload_size_bytes
    if file.size is not None and file.size > max_bytes:
        raise _invalid("Document exceeds the upload size limit", 413)

    # Always use a separate, random subdirectory under the configured temp root.
    staged = await run_in_threadpool(
        _stage_upload,
        file.file,
        container.settings.temp_dir,
        max_bytes,
        Path(filename).suffix.lower(),
    )
    try:
        source = SourceVersion(
            source=SourceRef(
                source_id=metadata.source_id,
                knowledge_space_id=metadata.knowledge_space_id,
                source_type="document",
            ),
            version=metadata.version,
        )
        execution_request = DocumentExecutionRequest(
            document=DocumentInput(source=source, content=ContentRef(uri=staged.path.as_uri())),
            filename=filename,
            content_type=content_type,
            size_bytes=staged.size_bytes,
            processing_profile=metadata.processing_profile,
        )
        try:
            result = await run_document_ingestion(
                executor,
                execution_request,
                timeout_seconds=container.settings.request_timeout_seconds,
            )
        except DocumentExecutionTimedOut as exc:
            raise ApplicationError(
                code=ErrorCode.PROCESSING_FAILED,
                message="Document processing timed out",
                status_code=504,
                retryable=True,
            ) from exc
        except DocumentExecutionFailed as exc:
            raise ApplicationError(
                code=ErrorCode.PROCESSING_FAILED,
                message="Document processing failed",
                status_code=500,
            ) from exc

        if not isinstance(result, DocumentExecutionResult) or (
            result.chunks_indexed is not None and result.chunks_indexed < 0
        ):
            raise ApplicationError(
                code=ErrorCode.PROCESSING_FAILED,
                message="Document processor returned an invalid result",
                status_code=500,
            )

        return DocumentUploadResponse(
            source_id=metadata.source_id,
            version=metadata.version,
            chunks_indexed=result.chunks_indexed,
            request_id=getattr(request.state, "request_id", None),
        )
    finally:
        await run_in_threadpool(shutil.rmtree, staged.work_dir)
