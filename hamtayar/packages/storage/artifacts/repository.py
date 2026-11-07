"""Local filesystem artifact repository for development and deterministic tests.

This implementation is *not* a distributed production object store. It uses
content-addressed opaque references and validates source ownership on reads.
Caller must authenticate/authorize the request before entering ingestion.
"""

import asyncio
import hashlib
import json
import os
import tempfile
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import ChunkingResult
from packages.contracts.common import ContentRef, SourceVersion
from packages.contracts.document import ParsedDocument
from packages.contracts.indexing import EmbeddingRecord


class ArtifactAccessError(PermissionError):
    """A reference does not belong to the supplied source/version."""


class ArtifactCorruptError(ValueError):
    """Stored bytes or metadata do not match the immutable reference."""


class LocalArtifactRepository:
    """Crash-safe-on-replacement, content-addressed local artifact storage.

    Filesystem durability and shared-host locking are not guaranteed: use an
    object-store implementation for distributed deployments and production.
    """

    def __init__(
        self, *, root: Path, allowed_roots: Sequence[Path],
        max_raw_bytes: int, tenant_id: str,
        max_artifact_bytes: int = 128 * 1024 * 1024,
    ) -> None:
        if max_raw_bytes < 1 or max_artifact_bytes < 1:
            raise ValueError('Artifact size limits must be positive')
        if not allowed_roots:
            raise ValueError('Explicit allowed_roots are required')
        if not tenant_id or not tenant_id.strip():
            raise ValueError("Trusted tenant_id is required")
        self.tenant_id = tenant_id
        self.root = Path(root).resolve()
        self.allowed_roots = tuple(Path(p).resolve() for p in allowed_roots)
        self.max_raw_bytes = max_raw_bytes
        self.max_artifact_bytes = max_artifact_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _source_key(source: SourceVersion) -> str:
        return json.dumps(source.model_dump(mode='json'), sort_keys=True, ensure_ascii=False)

    def _paths(self, token: str) -> tuple[Path, Path]:
        if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
            raise ArtifactAccessError('Invalid artifact reference')
        directory = self.root / token[:2]
        return directory / f'{token}.bin', directory / f'{token}.json'

    def _ref_token(self, ref: ContentRef) -> str:
        uri = urlsplit(ref.uri)
        if uri.scheme != 'artifact' or not uri.netloc or uri.path or uri.query or uri.fragment:
            raise ArtifactAccessError('Unsupported artifact reference')
        return uri.netloc

    def _write(self, source: SourceVersion, kind: str, data: bytes) -> ContentRef:
        if len(data) > self.max_artifact_bytes:
            raise ValueError('Artifact exceeds configured limit')
        source_key = self._source_key(source)
        digest = hashlib.sha256(data).hexdigest()
        token = hashlib.sha256(
            json.dumps([self.tenant_id, source_key, kind, digest], ensure_ascii=False).encode('utf-8')
        ).hexdigest()
        target, manifest = self._paths(token)
        target.parent.mkdir(parents=True, exist_ok=True)
        info = {
            'schema': 1, 'tenant': self.tenant_id,
            'source': source.model_dump(mode='json'),
            'kind': kind, 'sha256': digest, 'size': len(data),
        }
        # Atomic replacement avoids partial writes; same-key concurrent writers
        # write identical bytes and metadata, so the final value is stable.
        for dest, payload in ((target, data), (manifest, json.dumps(info, sort_keys=True).encode('utf-8'))):
            fd, temp = tempfile.mkstemp(dir=target.parent, prefix=f'.artifact-{token}-')
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, dest)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        return ContentRef(uri=f'artifact://{token}')

    def _read(self, ref: ContentRef, source: SourceVersion, kind: str) -> bytes:
        target, manifest = self._paths(self._ref_token(ref))
        if not target.is_file() or not manifest.is_file():
            raise FileNotFoundError('Artifact not found')
        try:
            info = json.loads(manifest.read_text(encoding='utf-8'))
            stored = SourceVersion.model_validate(info['source'])
        except (ValueError, KeyError, TypeError) as exc:
            raise ArtifactCorruptError('Invalid artifact manifest') from exc
        if stored != source or info.get('tenant') != self.tenant_id or info.get('kind') != kind:
            raise ArtifactAccessError('Artifact source/version/type mismatch')
        if (info.get('schema') != 1 or type(info.get('size')) is not int
                or info['size'] < 0 or info['size'] > self.max_artifact_bytes
                or type(info.get('sha256')) is not str):
            raise ArtifactCorruptError('Invalid artifact manifest fields')
        expected_token = hashlib.sha256(json.dumps([
            self.tenant_id, self._source_key(source), kind, info['sha256'],
        ], ensure_ascii=False).encode('utf-8')).hexdigest()
        if expected_token != self._ref_token(ref):
            raise ArtifactCorruptError('Artifact reference digest mismatch')
        if target.stat().st_size != info['size']:
            raise ArtifactCorruptError('Artifact size mismatch')
        data = target.read_bytes()
        if len(data) != info['size'] or hashlib.sha256(data).hexdigest() != info['sha256']:
            raise ArtifactCorruptError('Artifact integrity check failed')
        return data

    def _stage_sync(self, source: SourceVersion, original: ContentRef) -> ContentRef:
        parsed = urlsplit(original.uri)
        if parsed.scheme == 'artifact':
            self._read(original, source, 'raw')
            return original
        if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost') or parsed.query or parsed.fragment:
            raise ValueError('Only permitted file:// or existing artifact:// inputs are supported')
        path = Path(url2pathname(unquote(parsed.path))).resolve(strict=True)
        if not path.is_file() or not any(path.is_relative_to(root) for root in self.allowed_roots):
            raise ArtifactAccessError('File is outside explicitly allowed roots')
        if path.stat().st_size == 0:
            raise ValueError('Source file is empty')
        if path.stat().st_size > self.max_raw_bytes:
            raise ValueError('Source file exceeds size limit')
        content = bytearray()
        with path.open('rb') as stream:
            while part := stream.read(256 * 1024):
                content.extend(part)
                if len(content) > self.max_raw_bytes:
                    raise ValueError('Source file exceeds size limit')
        return self._write(source, 'raw', bytes(content))

    async def stage_raw(
        self, *, source: SourceVersion, original: ContentRef, access: AccessMetadata,
    ) -> ContentRef:
        AccessMetadata.model_validate(access)
        if access.tenant_id != self.tenant_id:
            raise ArtifactAccessError("Tenant is not permitted by repository scope")
        # AccessMetadata is not an authentication token. This method enforces
        # reference isolation; the caller is responsible for authenticating
        # source ownership before invoking it.
        return await asyncio.to_thread(self._stage_sync, source, original)

    @asynccontextmanager
    async def materialize_raw(
        self, *, ref: ContentRef, source: SourceVersion,
    ) -> AsyncIterator[Path]:
        # materialization is limited to immutable files under the repository;
        # do not delete these files while a checkpoint may need them.
        await asyncio.to_thread(self._read, ref, source, 'raw')
        path, _ = self._paths(self._ref_token(ref))
        yield path

    async def _put_model(self, source: SourceVersion, kind: str, model) -> ContentRef:
        data = model.model_dump_json().encode('utf-8')
        return await asyncio.to_thread(self._write, source, kind, data)

    async def _get_model(self, ref: ContentRef, source: SourceVersion, kind: str, cls):
        data = await asyncio.to_thread(self._read, ref, source, kind)
        return cls.model_validate_json(data)

    async def put_parsed(
        self, *, source: SourceVersion, document: ParsedDocument, stage: str,
    ) -> ContentRef:
        if stage not in ('parsed', 'normalized') or document.source != source:
            raise ValueError('Parsed artifact stage/source mismatch')
        return await self._put_model(source, stage, document)

    async def get_parsed(self, *, ref: ContentRef, source: SourceVersion) -> ParsedDocument:
        # Parsed and normalized artifacts share the same contract; the stored
        # manifest kind, not untrusted ref content, determines the accepted kind.
        kinds = ('normalized', 'parsed')
        for kind in kinds:
            try:
                return await self._get_model(ref, source, kind, ParsedDocument)
            except ArtifactAccessError:
                continue
        raise ArtifactAccessError('Not a parsed artifact for this source')

    async def put_chunks(self, *, source: SourceVersion, result: ChunkingResult) -> ContentRef:
        if any(chunk.source != source for chunk in result.chunks):
            raise ValueError('Chunk source mismatch')
        return await self._put_model(source, 'chunks', result)

    async def get_chunks(self, *, ref: ContentRef, source: SourceVersion) -> ChunkingResult:
        return await self._get_model(ref, source, 'chunks', ChunkingResult)

    async def put_embeddings(
        self, *, source: SourceVersion, records: Sequence[EmbeddingRecord],
    ) -> ContentRef:
        items = list(records)
        from pydantic import TypeAdapter
        adapter = TypeAdapter(list[EmbeddingRecord])
        data = adapter.dump_json(items)
        return await asyncio.to_thread(self._write, source, 'embeddings', data)

    async def get_embeddings(
        self, *, ref: ContentRef, source: SourceVersion,
    ) -> list[EmbeddingRecord]:
        from pydantic import TypeAdapter
        data = await asyncio.to_thread(self._read, ref, source, 'embeddings')
        return TypeAdapter(list[EmbeddingRecord]).validate_json(data)
