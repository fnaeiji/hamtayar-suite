
import asyncio

import pytest
from pydantic import ValidationError

from packages.access.metadata import resolve_access_metadata
from packages.contracts.access import AccessMetadata
from packages.contracts.common import SourceRef, SourceVersion


@pytest.fixture
def source():
    return SourceVersion(
        source=SourceRef(
            source_id="doc-101",
            knowledge_space_id="engineering",
            source_type="document",
        ),
        version="v1",
    )


class FakeProvider:
    """Simulate the authorization provider."""

    def __init__(self, metadata=None, error=None):
        self.metadata = metadata
        self.error = error
        self.received_source = None

    async def get_source_metadata(self, source):
        self.received_source = source

        if self.error:
            raise self.error

        return self.metadata


def test_metadata_returns_valid_access(source):
    expected = AccessMetadata(
        tenant_id="company-1",
        acl_principals=["team-hamtayar"],
    )
    provider = FakeProvider(metadata=expected)

    result = asyncio.run(
        resolve_access_metadata(source, provider)
    )

    assert result == expected
    assert provider.received_source == source


def test_metadata_rejects_empty_tenant(source):
    provider = FakeProvider(
        metadata={
            "tenant_id": "",
            "acl_principals": ["team-hamtayar"],
        }
    )

    with pytest.raises(ValidationError):
        asyncio.run(resolve_access_metadata(source, provider))


def test_metadata_rejects_empty_principals(source):
    provider = FakeProvider(
        metadata={
            "tenant_id": "company-1",
            "acl_principals": [],
        }
    )

    with pytest.raises(ValidationError):
        asyncio.run(resolve_access_metadata(source, provider))


def test_metadata_rejects_blank_principal(source):
    provider = FakeProvider(
        metadata=AccessMetadata(
            tenant_id="company-1",
            acl_principals=[" "],
        )
    )

    with pytest.raises(ValueError):
        asyncio.run(resolve_access_metadata(source, provider))


def test_metadata_rejects_blank_tenant(source):
    provider = FakeProvider(
        metadata=AccessMetadata(
            tenant_id=" ",
            acl_principals=["team-hamtayar"],
        )
    )

    with pytest.raises(ValueError):
        asyncio.run(resolve_access_metadata(source, provider))


def test_metadata_provider_failure_is_not_ignored(source):
    provider = FakeProvider(
        error=ConnectionError("Padeen unavailable")
    )

    with pytest.raises(ConnectionError):
        asyncio.run(resolve_access_metadata(source, provider))


def test_metadata_rejects_invalid_response(source):
    provider = FakeProvider(metadata={"unexpected": "data"})

    with pytest.raises(ValidationError):
        asyncio.run(resolve_access_metadata(source, provider))
