
import pytest
from pydantic import ValidationError

from packages.contracts.common import (
    ContentRef,
    SourceLocation,
    SourceRef,
    SourceVersion,
)


@pytest.fixture
def valid_source():
    """Create a reusable valid source."""

    return SourceRef(
        source_id="doc-101",
        knowledge_space_id="engineering",
        source_type="document",
    )


def test_source_ref_valid(valid_source):
    assert valid_source.source_id == "doc-101"
    assert valid_source.source_type == "document"


def test_source_ref_repository():
    source = SourceRef(
        source_id="repo-101",
        knowledge_space_id="engineering",
        source_type="repository",
    )

    assert source.source_type == "repository"


@pytest.mark.parametrize(
    "field",
    ["source_id", "knowledge_space_id"],
)
def test_source_ref_rejects_empty_identifiers(field):
    data = {
        "source_id": "doc-101",
        "knowledge_space_id": "engineering",
        "source_type": "document",
    }
    data[field] = ""

    with pytest.raises(ValidationError):
        SourceRef(**data)


def test_source_ref_rejects_invalid_type():
    with pytest.raises(ValidationError):
        SourceRef(
            source_id="source-101",
            knowledge_space_id="engineering",
            source_type="image",
        )


def test_source_ref_rejects_extra_fields():
    with pytest.raises(ValidationError):
        SourceRef(
            source_id="doc-101",
            knowledge_space_id="engineering",
            source_type="document",
            unknown_field="test",
        )


def test_source_version_valid(valid_source):
    version = SourceVersion(
        source=valid_source,
        version="v1",
    )

    assert version.source.source_id == "doc-101"
    assert version.version == "v1"


def test_source_version_rejects_empty_version(valid_source):
    with pytest.raises(ValidationError):
        SourceVersion(source=valid_source, version="")


def test_content_ref_valid():
    content = ContentRef(
        uri="padeen://documents/doc-101/v1"
    )

    assert content.uri.startswith("padeen://")


def test_content_ref_rejects_empty_uri():
    with pytest.raises(ValidationError):
        ContentRef(uri="")


def test_source_location_document():
    location = SourceLocation(
        page=5,
        section="Architecture",
    )

    assert location.page == 5
    assert location.section == "Architecture"


def test_source_location_code():
    location = SourceLocation(
        file_path="src/auth.py",
        start_line=10,
        end_line=25,
    )

    assert location.start_line == 10
    assert location.end_line == 25


@pytest.mark.parametrize(
    "data",
    [
        {"page": 0},
        {"start_line": 0},
        {"end_line": 0},
        {"start_line": 20, "end_line": 10},
        {"end_line": 20},
    ],
)
def test_source_location_rejects_invalid_values(data):
    with pytest.raises(ValidationError):
        SourceLocation(**data)


def test_source_location_allows_optional_fields():
    location = SourceLocation()

    assert location.page is None
    assert location.file_path is None


def test_source_version_json_round_trip(valid_source):
    original = SourceVersion(
        source=valid_source,
        version="v2",
    )

    json_data = original.model_dump_json()
    restored = SourceVersion.model_validate_json(json_data)

    assert restored == original


def test_source_location_excludes_none_fields():
    location = SourceLocation(page=3)

    data = location.model_dump(exclude_none=True)

    assert data == {"page": 3}
