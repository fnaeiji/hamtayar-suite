"""Validated Knowledge settings loaded explicitly from TOML and overrides."""

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_KNOWLEDGE_CONFIG_PATH = Path(__file__).parents[2] / "config" / "knowledge.toml"
DEFAULT_EMBEDDING_MODEL_ID = "BAAI/bge-m3"


class _StrictSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ChunkingSettings(_StrictSettings):
    """Configuration for the future structure-aware v1 chunker."""

    strategy: Literal["structure_aware"] = "structure_aware"
    profile: Literal["structure_aware_v1"] = "structure_aware_v1"
    max_tokens: int = Field(default=512, strict=True, gt=0)
    overlap_tokens: int = Field(default=0, strict=True)
    oversized_content_policy: Literal["error"] = "error"

    @model_validator(mode="after")
    def validate_v1_overlap(self) -> "ChunkingSettings":
        if self.overlap_tokens != 0:
            raise ValueError("overlap_tokens must be 0 for structure_aware_v1")
        return self


TokenizerBackend = Literal["huggingface_tokenizers"]


class EmbeddingSettings(_StrictSettings):
    """Expected embedding configuration; does not load or validate artifacts."""

    model_id: str = DEFAULT_EMBEDDING_MODEL_ID
    model_revision: str | None = None
    tokenizer_id: str | None = None
    tokenizer_revision: str | None = None
    tokenizer_backend: TokenizerBackend = "huggingface_tokenizers"
    tokenizer_cache_dir: str | None = None
    tokenizer_local_files_only: bool = False
    include_special_tokens: bool = True
    output_mode: Literal["dense"] = "dense"
    dimensions: int = Field(default=1024, strict=True, gt=0)
    normalize_embeddings: bool = True

    @model_validator(mode="before")
    @classmethod
    def resolve_tokenizer_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        values = dict(data)
        model_id = values.get("model_id", DEFAULT_EMBEDDING_MODEL_ID)
        if values.get("tokenizer_id") is None:
            values["tokenizer_id"] = model_id
        if (
            values.get("tokenizer_revision") is None
            and values["tokenizer_id"] == model_id
        ):
            values["tokenizer_revision"] = values.get("model_revision")
        return values

    @model_validator(mode="after")
    def validate_identifiers(self) -> "EmbeddingSettings":
        if not self.model_id.strip():
            raise ValueError("model_id must not be blank")
        if self.tokenizer_id is None or not self.tokenizer_id.strip():
            raise ValueError("tokenizer_id must not be blank")
        if self.model_revision is not None and not self.model_revision.strip():
            raise ValueError("model_revision must not be blank when supplied")
        if self.tokenizer_revision is not None and not self.tokenizer_revision.strip():
            raise ValueError("tokenizer_revision must not be blank when supplied")
        if (
            self.tokenizer_cache_dir is not None
            and not self.tokenizer_cache_dir.strip()
        ):
            raise ValueError("tokenizer_cache_dir must not be blank when supplied")
        return self


class KnowledgeConfiguration(_StrictSettings):
    """Validated chunking and embedding settings from one source."""

    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)


def load_knowledge_configuration(
    path: str | Path = DEFAULT_KNOWLEDGE_CONFIG_PATH,
    *,
    overrides: Mapping[str, Mapping[str, object]] | None = None,
) -> KnowledgeConfiguration:
    """Load settings on demand; overrides take precedence over TOML and defaults.

    TOML keys are strict and unknown sections or fields fail validation. The
    caller owns environment lookup and passes supported overrides explicitly.
    Missing files and malformed TOML are surfaced to the caller.
    """
    config_path = Path(path)
    with config_path.open("rb") as config_file:
        data = tomllib.load(config_file)

    if overrides:
        unknown_sections = set(overrides) - {"chunking", "embedding"}
        if unknown_sections:
            names = ", ".join(sorted(unknown_sections))
            raise ValueError(
                f"Unknown Knowledge configuration override section(s): {names}"
            )
        for section, values in overrides.items():
            if not isinstance(values, Mapping):
                raise TypeError(f"Override section {section!r} must be a mapping")
            current = data.setdefault(section, {})
            if not isinstance(current, dict):
                raise TypeError(f"Configuration section {section!r} must be a table")
            if (
                section == "embedding"
                and "model_id" in values
                and values["model_id"]
                != current.get("model_id", DEFAULT_EMBEDDING_MODEL_ID)
                and "model_revision" not in values
            ):
                # A commit ID belongs to a repository; never carry the file's pin
                # onto a different embedding repository selected by an override.
                current["model_revision"] = None
            current.update(values)

    return KnowledgeConfiguration.model_validate(data)
