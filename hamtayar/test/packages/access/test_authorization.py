
import asyncio

import pytest

from packages.access.authorization import reauthorize_results
from packages.contracts.access import TrustedAccessContext
from packages.contracts.common import SourceRef, SourceVersion
from packages.contracts.retrieval import SearchResult


@pytest.fixture
def context():
    return TrustedAccessContext(
        subject_id="user-101",
        tenant_id="company-1",
        principals=["user-101", "team-hamtayar"],
    )


def make_source(source_id, version="v1", source_type="document"):
    """Create a source version for authorization tests."""

    return SourceVersion(
        source=SourceRef(
            source_id=source_id,
            knowledge_space_id="engineering",
            source_type=source_type,
        ),
        version=version,
    )


def make_result(source, evidence_id):
    """Create a retrieval result."""

    return SearchResult(
        evidence_id=evidence_id,
        source=source,
        generation_id="gen-001",
        retrieval_method="hybrid",
        text="Sample evidence",
    )


class FakeProvider:
    """Simulate source authorization decisions."""

    def __init__(self, allowed=None, error=None):
        self.allowed = allowed or []
        self.error = error
        self.received_sources = None
        self.calls = 0

    async def authorize_sources(self, context, sources):
        self.calls += 1
        self.received_sources = sources

        if self.error:
            raise self.error

        return self.allowed


def test_authorization_returns_allowed_results(context):
    source = make_source("doc-101")
    result = make_result(source, "chunk-101")
    provider = FakeProvider(allowed=[source])

    output = asyncio.run(
        reauthorize_results([result], context, provider)
    )

    assert output == [result]


def test_authorization_removes_denied_results(context):
    allowed = make_source("doc-101")
    denied = make_source("doc-102")

    results = [
        make_result(allowed, "chunk-101"),
        make_result(denied, "chunk-102"),
    ]

    provider = FakeProvider(allowed=[allowed])

    output = asyncio.run(
        reauthorize_results(results, context, provider)
    )

    assert len(output) == 1
    assert output[0].evidence_id == "chunk-101"


def test_authorization_denies_everything(context):
    source = make_source("doc-101")
    provider = FakeProvider(allowed=[])

    output = asyncio.run(
        reauthorize_results(
            [make_result(source, "chunk-101")],
            context,
            provider,
        )
    )

    assert output == []


def test_authorization_deduplicates_sources(context):
    source = make_source("doc-101")
    results = [
        make_result(source, "chunk-101"),
        make_result(source, "chunk-102"),
    ]
    provider = FakeProvider(allowed=[source])

    output = asyncio.run(
        reauthorize_results(results, context, provider)
    )

    assert len(provider.received_sources) == 1
    assert len(output) == 2


def test_authorization_respects_source_version(context):
    v1 = make_source("doc-101", "v1")
    v2 = make_source("doc-101", "v2")

    provider = FakeProvider(allowed=[v1])

    output = asyncio.run(
        reauthorize_results(
            [
                make_result(v1, "chunk-101"),
                make_result(v2, "chunk-102"),
            ],
            context,
            provider,
        )
    )

    assert len(output) == 1
    assert output[0].source.version == "v1"


def test_authorization_rejects_unexpected_sources(context):
    requested = make_source("doc-101")
    unexpected = make_source("doc-999")

    provider = FakeProvider(allowed=[unexpected])

    with pytest.raises(ValueError):
        asyncio.run(
            reauthorize_results(
                [make_result(requested, "chunk-101")],
                context,
                provider,
            )
        )


def test_authorization_provider_failure_is_not_ignored(context):
    source = make_source("doc-101")
    provider = FakeProvider(
        error=ConnectionError("Padeen unavailable")
    )

    with pytest.raises(ConnectionError):
        asyncio.run(
            reauthorize_results(
                [make_result(source, "chunk-101")],
                context,
                provider,
            )
        )


def test_authorization_skips_provider_for_empty_results(context):
    provider = FakeProvider()

    output = asyncio.run(
        reauthorize_results([], context, provider)
    )

    assert output == []
    assert provider.calls == 0


def test_authorization_does_not_confuse_source_types(context):
    document = make_source(
        "source-101",
        source_type="document",
    )
    repository = make_source(
        "source-101",
        source_type="repository",
    )

    provider = FakeProvider(allowed=[document])

    output = asyncio.run(
        reauthorize_results(
            [
                make_result(document, "chunk-document"),
                make_result(repository, "chunk-repository"),
            ],
            context,
            provider,
        )
    )

    assert [item.evidence_id for item in output] == [
        "chunk-document"
    ]
