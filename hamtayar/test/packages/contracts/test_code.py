
import pytest
from pydantic import ValidationError

from packages.contracts.code import (
    CodeAnalysisRequest,
    CodeAnalysisResult,
    CodeRelationship,
    CodeSymbol,
)
from packages.contracts.common import (
    ContentRef,
    SourceLocation,
    SourceRef,
    SourceVersion,
)


@pytest.fixture
def source_version():
    """Create a valid repository source version."""

    return SourceVersion(
        source=SourceRef(
            source_id="repo-101",
            knowledge_space_id="engineering",
            source_type="repository",
        ),
        version="commit-abc123",
    )


@pytest.fixture
def valid_result(source_version):
    """Create a valid code analysis result."""

    return CodeAnalysisResult(
        source=source_version,
        provider_id="internal",
        symbols=[
            CodeSymbol(
                symbol_id="sym-1",
                name="UserService",
                kind="class",
                location=SourceLocation(
                    file_path="src/users.py",
                    start_line=1,
                    end_line=10,
                ),
            ),
            CodeSymbol(
                symbol_id="sym-2",
                name="get_user",
                kind="method",
                location=SourceLocation(
                    file_path="src/users.py",
                    start_line=3,
                    end_line=5,
                ),
            ),
        ],
        relationships=[
            CodeRelationship(
                source_symbol_id="sym-1",
                target_symbol_id="sym-2",
                kind="CONTAINS",
            ),
        ],
    )


# CodeAnalysisRequest tests

def test_analysis_request_valid(source_version):
    request = CodeAnalysisRequest(
        source=source_version,
        content=ContentRef(uri="padeen://repositories/repo-101"),
        provider_id="gitnexus",
    )

    assert request.source.version == "commit-abc123"
    assert request.provider_id == "gitnexus"


def test_analysis_request_default_provider(source_version):
    request = CodeAnalysisRequest(
        source=source_version,
        content=ContentRef(uri="padeen://repositories/repo-101"),
    )

    assert request.provider_id == "internal"


def test_analysis_request_requires_content(source_version):
    with pytest.raises(ValidationError):
        CodeAnalysisRequest(source=source_version)


def test_analysis_request_rejects_invalid_version(source_version):
    with pytest.raises(ValidationError):
        CodeAnalysisRequest(
            source={
                "source": source_version.source.model_dump(),
                "version": "",
            },
            content=ContentRef(uri="padeen://repositories/repo-101"),
        )


# CodeSymbol tests

def test_code_symbol_valid():
    symbol = CodeSymbol(
        symbol_id="sym-1",
        name="UserService",
        kind="class",
        location=SourceLocation(
            file_path="src/users.py",
            start_line=1,
            end_line=10,
        ),
        signature="class UserService",
    )

    assert symbol.name == "UserService"
    assert symbol.location.start_line == 1
    assert symbol.signature == "class UserService"


def test_code_symbol_optional_fields():
    symbol = CodeSymbol(
        symbol_id="sym-1",
        name="get_user",
        kind="method",
        location=SourceLocation(file_path="src/users.py"),
    )

    assert symbol.signature is None
    assert symbol.content is None


def test_code_symbol_requires_location():
    with pytest.raises(ValidationError):
        CodeSymbol(
            symbol_id="sym-1",
            name="get_user",
            kind="method",
        )


def test_code_symbol_rejects_invalid_line_range():
    with pytest.raises(ValidationError):
        CodeSymbol(
            symbol_id="sym-1",
            name="get_user",
            kind="method",
            location={
                "file_path": "src/users.py",
                "start_line": 20,
                "end_line": 10,
            },
        )


# CodeRelationship tests

@pytest.mark.parametrize(
    "relationship_type",
    ["CONTAINS", "IMPORTS", "DEFINES", "EXTENDS"],
)
def test_relationship_accepts_supported_types(relationship_type):
    relationship = CodeRelationship(
        source_symbol_id="sym-1",
        target_symbol_id="sym-2",
        kind=relationship_type,
    )

    assert relationship.kind == relationship_type


def test_relationship_rejects_unsupported_type():
    with pytest.raises(ValidationError):
        CodeRelationship(
            source_symbol_id="sym-1",
            target_symbol_id="sym-2",
            kind="CALLS",
        )


# CodeAnalysisResult tests

def test_analysis_result_valid(valid_result):
    assert len(valid_result.symbols) == 2
    assert len(valid_result.relationships) == 1
    assert valid_result.provider_id == "internal"


def test_analysis_result_preserves_relationships(valid_result):
    relationship = valid_result.relationships[0]

    assert relationship.kind == "CONTAINS"
    assert relationship.source_symbol_id == "sym-1"
    assert relationship.target_symbol_id == "sym-2"


def test_analysis_result_defaults(source_version):
    result = CodeAnalysisResult(
        source=source_version,
        provider_id="internal",
    )

    assert result.symbols == []
    assert result.relationships == []
    assert result.warnings == []
    assert result.index_handle is None


def test_analysis_result_backend_provider(source_version):
    result = CodeAnalysisResult(
        source=source_version,
        provider_id="gitnexus",
        index_handle="index-101",
        index_generation="gen-1",
    )

    assert result.index_handle == "index-101"
    assert result.index_generation == "gen-1"


def test_analysis_result_preserves_warnings(source_version):
    result = CodeAnalysisResult(
        source=source_version,
        provider_id="internal",
        warnings=["Unsupported language detected"],
    )

    assert len(result.warnings) == 1


def test_analysis_result_rejects_invalid_symbol(source_version):
    with pytest.raises(ValidationError):
        CodeAnalysisResult(
            source=source_version,
            provider_id="internal",
            symbols=[
                {
                    "symbol_id": "sym-1",
                    "name": "UserService",
                    "kind": "class",
                }
            ],
        )


def test_analysis_result_rejects_extra_fields(source_version):
    with pytest.raises(ValidationError):
        CodeAnalysisResult(
            source=source_version,
            provider_id="internal",
            unknown_field="test",
        )


def test_analysis_result_json_round_trip(valid_result):
    json_data = valid_result.model_dump_json()
    restored = CodeAnalysisResult.model_validate_json(json_data)

    assert restored == valid_result
