
import pytest
from pydantic import ValidationError

from packages.contracts.access import (
    AccessMetadata,
    AccessScope,
)
from packages.contracts.answering import (
    AnswerRequest,
    AnswerResponse,
    Citation,
)
from packages.contracts.chunks import (
    Chunk,
    ChunkingItem,
    ChunkingRequest,
    ChunkingResult,
)
from packages.contracts.common import (
    ContentRef,
    SourceLocation,
    SourceRef,
    SourceVersion,
)
from packages.contracts.document import (
    DocumentBlock,
    DocumentInput,
    ParsedDocument,
)
from packages.contracts.indexing import (
    EmbeddingRecord,
    IndexingRequest,
    IndexingResult,
    PublicationRequest,
    PublicationResult,
)
from packages.contracts.retrieval import (
    RetrievalQuery,
    RetrievalResponse,
    SearchRequest,
    SearchResult,
)


@pytest.fixture
def source_version():
    """Create a shared source version for the flow."""

    return SourceVersion(
        source=SourceRef(
            source_id="doc-101",
            knowledge_space_id="engineering",
            source_type="document",
        ),
        version="v1",
    )


@pytest.fixture
def access_metadata():
    """Create trusted document access metadata."""

    return AccessMetadata(
        tenant_id="company-1",
        acl_principals=["team-hamtayar"],
    )


@pytest.fixture
def parsed_document(source_version):
    """Simulate the output of document parsing."""

    return ParsedDocument(
        source=source_version,
        blocks=[
            DocumentBlock(
                block_type="heading",
                text="System Architecture",
                location=SourceLocation(page=1),
            ),
            DocumentBlock(
                block_type="paragraph",
                text="Hamtayar is an enterprise RAG system.",
                location=SourceLocation(page=2),
            ),
        ],
        metadata={"language": "en"},
    )


@pytest.fixture
def chunk(parsed_document, access_metadata):
    """Simulate a chunk produced by Knowledge."""

    block = parsed_document.blocks[1]

    return Chunk(
        chunk_id="chunk-101",
        source=parsed_document.source,
        kind="document",
        text=block.text,
        location=block.location,
        access=access_metadata,
    )


@pytest.fixture
def indexing_request(source_version, chunk):
    """Create an indexing request from a chunk."""

    return IndexingRequest(
        source=source_version,
        generation_id="gen-001",
        chunks=[chunk],
        embeddings=[
            EmbeddingRecord(
                chunk_id=chunk.chunk_id,
                model_id="embedding-v1",
                vector=[0.1, 0.2, 0.3],
            ),
        ],
    )


# Document parsing boundary

def test_document_input_to_parsed_document(
    source_version,
    parsed_document,
):
    document_input = DocumentInput(
        source=source_version,
        content=ContentRef(
            uri="padeen://documents/doc-101/v1"
        ),
    )

    assert parsed_document.source == document_input.source
    assert len(parsed_document.blocks) == 2
    assert parsed_document.blocks[1].location.page == 2


# Document to chunking boundary

def test_parsed_document_to_chunking_request(
    parsed_document,
    access_metadata,
):
    request = ChunkingRequest(
        source=parsed_document.source,
        kind="document",
        items=[
            ChunkingItem(
                text=block.text,
                location=block.location,
            )
            for block in parsed_document.blocks
        ],
        access=access_metadata,
    )

    assert len(request.items) == 2
    assert request.source == parsed_document.source
    assert request.items[1].location.page == 2
    assert request.access.tenant_id == "company-1"


def test_chunk_preserves_source_and_access(
    parsed_document,
    access_metadata,
    chunk,
):
    result = ChunkingResult(chunks=[chunk])

    assert len(result.chunks) == 1
    assert chunk.source == parsed_document.source
    assert chunk.text == parsed_document.blocks[1].text
    assert chunk.access == access_metadata
    assert chunk.location.page == 2


# Chunk to indexing boundary

def test_chunk_to_indexing_request(
    indexing_request,
    chunk,
):
    assert len(indexing_request.chunks) == 1
    assert len(indexing_request.embeddings) == 1

    indexed_chunk = indexing_request.chunks[0]
    embedding = indexing_request.embeddings[0]

    assert indexed_chunk.chunk_id == embedding.chunk_id
    assert indexed_chunk.access.tenant_id == "company-1"
    assert indexed_chunk.source == indexing_request.source


def test_invalid_access_rejected_at_indexing_boundary(
    indexing_request,
):
    data = indexing_request.model_dump()

    data["chunks"][0]["access"]["acl_principals"] = []

    with pytest.raises(ValidationError):
        IndexingRequest.model_validate(data)


# Indexing to publication boundary

def test_indexing_result_to_publication(
    indexing_request,
):
    result = IndexingResult(
        generation_id=indexing_request.generation_id,
        indexed_count=1,
        validated=True,
    )

    assert result.validated is True

    publication_request = PublicationRequest(
        source=indexing_request.source,
        generation_id=result.generation_id,
    )

    publication_result = PublicationResult(
        generation_id=publication_request.generation_id,
        published=True,
    )

    assert publication_result.published is True
    assert publication_result.generation_id == (
        indexing_request.generation_id
    )


# Authorized retrieval boundary

def test_retrieval_query_preserves_authorized_scope(
    indexing_request,
):
    scope = AccessScope(
        tenant_id="company-1",
        principals=["team-hamtayar"],
        source_ids=["doc-101"],
    )

    query = RetrievalQuery(
        request=SearchRequest(
            query="What is Hamtayar?",
            mode="hybrid",
            top_k=5,
        ),
        scope=scope,
        generation_ids=[indexing_request.generation_id],
    )

    assert query.scope.tenant_id == "company-1"
    assert query.scope.source_ids == ["doc-101"]
    assert query.generation_ids == ["gen-001"]


# Retrieval to answering boundary

def test_retrieval_result_to_answer(chunk, indexing_request):
    search_result = SearchResult(
        evidence_id=chunk.chunk_id,
        source=chunk.source,
        generation_id=indexing_request.generation_id,
        retrieval_method="hybrid",
        text=chunk.text,
        location=chunk.location,
        score=0.95,
    )

    retrieval_response = RetrievalResponse(
        results=[search_result],
    )

    answer_request = AnswerRequest(
        question="What is Hamtayar?",
        evidence=retrieval_response.results,
    )

    evidence = answer_request.evidence[0]

    citation = Citation(
        evidence_id=evidence.evidence_id,
        source=evidence.source,
        location=evidence.location,
    )

    answer_response = AnswerResponse(
        answer="Hamtayar is an enterprise RAG system.",
        citations=[citation],
        status="completed",
    )

    assert answer_response.status == "completed"
    assert answer_response.citations[0].evidence_id == (
        chunk.chunk_id
    )
    assert answer_response.citations[0].source == chunk.source
    assert answer_response.citations[0].location.page == 2


# Serialization across module boundaries

def test_indexing_request_json_round_trip(indexing_request):
    serialized = indexing_request.model_dump_json()

    restored = IndexingRequest.model_validate_json(serialized)

    assert restored == indexing_request
    assert restored.chunks[0].access.acl_principals == [
        "team-hamtayar"
    ]


def test_parsed_document_json_round_trip(parsed_document):
    serialized = parsed_document.model_dump_json()

    restored = ParsedDocument.model_validate_json(serialized)

    assert restored == parsed_document
    assert restored.blocks[1].location.page == 2


def test_invalid_nested_source_rejected_in_answer_request(
    chunk,
    indexing_request,
):
    evidence = SearchResult(
        evidence_id=chunk.chunk_id,
        source=chunk.source,
        generation_id=indexing_request.generation_id,
        retrieval_method="hybrid",
        text=chunk.text,
    )

    data = {
        "question": "What is Hamtayar?",
        "evidence": [evidence.model_dump()],
    }

    data["evidence"][0]["source"]["version"] = ""

    with pytest.raises(ValidationError):
        AnswerRequest.model_validate(data)
