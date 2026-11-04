import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.knowledge.configuration import (
    DEFAULT_KNOWLEDGE_CONFIG_PATH,
    ChunkingSettings,
    EmbeddingSettings,
    KnowledgeConfiguration,
)
from packages.knowledge.service import load_configuration


def _write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "knowledge.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_checked_in_configuration_contains_initial_defaults():
    config = load_configuration()

    assert DEFAULT_KNOWLEDGE_CONFIG_PATH.is_file()
    assert config.chunking.strategy == "structure_aware"
    assert config.chunking.profile == "structure_aware_v1"
    assert config.chunking.max_tokens == 512
    assert config.chunking.overlap_tokens == 0
    assert config.chunking.oversized_content_policy == "error"
    assert config.embedding.model_id == "BAAI/bge-m3"
    assert config.embedding.model_revision == "5617a9f61b028005a4858fdac845db406aefb181"
    assert config.embedding.tokenizer_id == config.embedding.model_id
    assert config.embedding.tokenizer_revision == config.embedding.model_revision
    assert config.embedding.tokenizer_backend == "huggingface_tokenizers"
    assert config.embedding.tokenizer_cache_dir is None
    assert config.embedding.tokenizer_local_files_only is False
    assert config.embedding.include_special_tokens is True
    assert config.embedding.output_mode == "dense"
    assert config.embedding.dimensions == 1024
    assert config.embedding.normalize_embeddings is True


def test_chunking_and_embedding_sections_override_independently(tmp_path):
    path = _write_config(
        tmp_path,
        """
[chunking]
max_tokens = 256

[embedding]
model_id = "example/model"
dimensions = 768
""",
    )

    chunking_override = load_configuration(
        path, overrides={"chunking": {"max_tokens": 128}}
    )
    embedding_override = load_configuration(
        path, overrides={"embedding": {"dimensions": 384}}
    )

    assert chunking_override.chunking.max_tokens == 128
    assert chunking_override.embedding.model_id == "example/model"
    assert chunking_override.embedding.dimensions == 768
    assert embedding_override.chunking.max_tokens == 256
    assert embedding_override.embedding.dimensions == 384


def test_existing_environment_override_wins_over_file(tmp_path, monkeypatch):
    pytest.importorskip("pydantic_settings")
    from apps.core.config import Settings, load_knowledge_settings

    path = _write_config(tmp_path, '[embedding]\nmodel_id = "file/model"\n')
    monkeypatch.setenv("HAMTAYAR_KNOWLEDGE_CONFIG_PATH", str(path))
    monkeypatch.setenv("HAMTAYAR_EMBEDDING_MODEL", "environment/model")
    settings = Settings()

    config = load_knowledge_settings(settings)

    assert config.embedding.model_id == "environment/model"
    assert config.embedding.tokenizer_id == "environment/model"


def test_explicit_tokenizer_and_revision_are_preserved():
    config = EmbeddingSettings(
        model_id="example/model",
        model_revision="model-sha",
        tokenizer_id="example/tokenizer",
        tokenizer_revision="tokenizer-sha",
    )

    assert config.tokenizer_id == "example/tokenizer"
    assert config.tokenizer_revision == "tokenizer-sha"


def test_tokenizer_revision_defaults_to_model_revision():
    config = EmbeddingSettings(
        model_id="example/model", model_revision="exact-revision"
    )

    assert config.tokenizer_id == "example/model"
    assert config.tokenizer_revision == "exact-revision"


def test_same_repository_inherits_model_revision():
    config = EmbeddingSettings(
        model_id="example/model",
        model_revision="model-sha",
        tokenizer_id="example/model",
    )

    assert config.tokenizer_revision == "model-sha"


def test_different_tokenizer_repository_does_not_inherit_model_revision():
    config = EmbeddingSettings(
        model_id="example/model",
        model_revision="model-sha",
        tokenizer_id="example/tokenizer",
    )

    assert config.tokenizer_revision is None


def test_different_tokenizer_repository_keeps_explicit_revision():
    config = EmbeddingSettings(
        model_id="example/model",
        model_revision="model-sha",
        tokenizer_id="example/tokenizer",
        tokenizer_revision="tokenizer-sha",
    )

    assert config.tokenizer_revision == "tokenizer-sha"


def test_model_override_resolves_unspecified_tokenizer_to_effective_model(tmp_path):
    path = _write_config(
        tmp_path,
        '[embedding]\nmodel_id = "file/model"\nmodel_revision = "file-revision"\n',
    )

    config = load_configuration(
        path, overrides={"embedding": {"model_id": "override/model"}}
    )

    assert config.embedding.model_id == "override/model"
    assert config.embedding.tokenizer_id == "override/model"
    assert config.embedding.model_revision is None
    assert config.embedding.tokenizer_revision is None


@pytest.mark.parametrize(
    "value",
    ["transformers", "sentence_transformers", "other"],
)
def test_unsupported_tokenizer_backends_are_rejected(value):
    with pytest.raises(ValidationError):
        EmbeddingSettings(tokenizer_backend=value)


@pytest.mark.parametrize("value", ["true", 1, 0])
def test_tokenizer_settings_require_strict_booleans(value):
    with pytest.raises(ValidationError):
        EmbeddingSettings(tokenizer_local_files_only=value)
    with pytest.raises(ValidationError):
        EmbeddingSettings(include_special_tokens=value)


def test_blank_tokenizer_cache_path_is_rejected():
    with pytest.raises(ValidationError, match="tokenizer_cache_dir must not be blank"):
        EmbeddingSettings(tokenizer_cache_dir="  ")


@pytest.mark.parametrize("field", ["model_revision", "tokenizer_revision"])
@pytest.mark.parametrize("revision", ["", "  \t  "])
def test_blank_revisions_are_rejected(field, revision):
    with pytest.raises(ValidationError, match="must not be blank"):
        EmbeddingSettings(model_id="example/model", **{field: revision})


@pytest.mark.parametrize("value", [0, -1, True, False, "512", 1.5])
def test_max_tokens_requires_a_strictly_positive_integer(value):
    with pytest.raises(ValidationError):
        ChunkingSettings(max_tokens=value)


@pytest.mark.parametrize("value", [True, False, "0", 1.5])
def test_overlap_tokens_requires_an_integer(value):
    with pytest.raises(ValidationError):
        ChunkingSettings(overlap_tokens=value)


@pytest.mark.parametrize("value", [-1, 1, 2])
def test_v1_rejects_nonzero_overlap(value):
    with pytest.raises(ValidationError, match="overlap_tokens must be 0"):
        ChunkingSettings(overlap_tokens=value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("strategy", "recursive"),
        ("oversized_content_policy", "split"),
        ("profile", "v2"),
    ],
)
def test_unknown_chunking_options_are_rejected(field, value):
    with pytest.raises(ValidationError):
        ChunkingSettings.model_validate({field: value})


@pytest.mark.parametrize("field", ["model_id", "tokenizer_id"])
@pytest.mark.parametrize("value", ["", "  \t  "])
def test_blank_model_and_tokenizer_identifiers_are_rejected(field, value):
    values = {field: value}
    if field == "tokenizer_id":
        values["model_id"] = "example/model"
    with pytest.raises(ValidationError):
        EmbeddingSettings.model_validate(values)


@pytest.mark.parametrize("value", [0, -1, True, "1024", 1.5])
def test_embedding_dimensions_require_a_strictly_positive_integer(value):
    with pytest.raises(ValidationError):
        EmbeddingSettings(dimensions=value)


@pytest.mark.parametrize("value", ["true", 1, 0])
def test_normalize_embeddings_requires_a_boolean(value):
    with pytest.raises(ValidationError):
        EmbeddingSettings(normalize_embeddings=value)


@pytest.mark.parametrize(
    "text",
    [
        "[chunking]\nmax_token = 256\n",
        '[embedding]\nmodel = "typo"\n',
        "[unknown]\nvalue = 1\n",
    ],
)
def test_unknown_configuration_keys_are_rejected(tmp_path, text):
    with pytest.raises(ValidationError, match="extra_forbidden"):
        load_configuration(_write_config(tmp_path, text))


def test_malformed_toml_is_reported(tmp_path):
    path = _write_config(tmp_path, "[chunking\nmax_tokens = 10\n")

    with pytest.raises(tomllib.TOMLDecodeError):
        load_configuration(path)


def test_missing_configuration_file_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_configuration(tmp_path / "missing.toml")


def test_unknown_override_keys_are_rejected():
    with pytest.raises(ValueError, match="Unknown Knowledge configuration override"):
        load_configuration(overrides={"chunk": {"max_tokens": 10}})


def test_configuration_models_reject_mutation():
    config = KnowledgeConfiguration()

    with pytest.raises(ValidationError):
        config.chunking.max_tokens = 10


def test_importing_configuration_does_not_load_settings_or_open_network_connections():
    script = """
import socket
import sys
from pathlib import Path
import pydantic

_ = (pydantic.BaseModel, pydantic.ConfigDict, pydantic.Field, pydantic.model_validator)
configuration_file = Path.cwd() / "config" / "knowledge.toml"
original_open = Path.open
original_create_connection = socket.create_connection

def guarded_open(self, *args, **kwargs):
    if self == configuration_file:
        raise AssertionError("configuration import loaded the TOML settings")
    return original_open(self, *args, **kwargs)

def unexpected_network(*args, **kwargs):
    raise AssertionError("configuration import opened a network connection")

Path.open = guarded_open
socket.create_connection = unexpected_network
import packages.knowledge.configuration
assert "tokenizers" not in sys.modules
assert "huggingface_hub" not in sys.modules
Path.open = original_open
socket.create_connection = original_create_connection
from packages.knowledge.service import load_configuration
load_configuration()
assert "tokenizers" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True)
