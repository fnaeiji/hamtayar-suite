"""Lazy Hugging Face tokenizer adapter shared by Knowledge capabilities."""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal, Protocol

from packages.knowledge.configuration import EmbeddingSettings

CapacityStatus = Literal["known", "unavailable", "sentinel", "invalid", "unloaded"]
MAX_LENGTH_SENTINEL = 10**20


@dataclass(frozen=True)
class TokenizerIdentity:
    """Configured and resolved tokenizer metadata for diagnostics."""

    backend: str
    tokenizer_id: str
    configured_revision: str | None
    resolved_revision: str | None = None
    vocabulary_size: int | None = None
    model_input_capacity: int | None = None
    capacity_status: CapacityStatus = "unloaded"


class TokenizerEncoding(Protocol):
    ids: Sequence[int]


class TokenizerEngine(Protocol):
    """Small surface consumed from the Rust tokenizers implementation."""

    def no_padding(self) -> None: ...

    def no_truncation(self) -> None: ...

    def encode(
        self, text: str, *, add_special_tokens: bool = True
    ) -> TokenizerEncoding: ...

    def get_vocab_size(self, with_added_tokens: bool = True) -> int: ...


@dataclass(frozen=True)
class LoadedTokenizer:
    engine: TokenizerEngine
    identity: TokenizerIdentity


TokenizerLoader = Callable[[EmbeddingSettings], LoadedTokenizer]


class TokenCounter(Protocol):
    """Replaceable counting capability used by chunking and future embedding."""

    @property
    def identity(self) -> TokenizerIdentity: ...

    def count_tokens(self, text: str, *, include_special_tokens: bool) -> int: ...


class TokenizerLoadError(RuntimeError):
    """The configured tokenizer could not be initialized."""


class TokenizerArtifactsUnavailable(TokenizerLoadError):
    """The selected tokenizer files are absent or could not be resolved."""


class TokenizerConfigurationError(ValueError):
    """Tokenizer metadata conflicts with validated Knowledge settings."""


class HuggingFaceTokenizer:
    """Load tokenizer JSON lazily and reuse it for this adapter instance.

    Only tokenizer artifacts are read. No Transformers pipeline, remote custom
    code, embedding model, or model weights are loaded.
    """

    def __init__(
        self,
        settings: EmbeddingSettings,
        *,
        loader: TokenizerLoader | None = None,
    ) -> None:
        self._settings = settings
        self._loader = loader or _load_huggingface_tokenizer
        self._loaded: LoadedTokenizer | None = None
        self._load_lock = Lock()

    @property
    def identity(self) -> TokenizerIdentity:
        if self._loaded is not None:
            return self._loaded.identity
        return TokenizerIdentity(
            backend=self._settings.tokenizer_backend,
            tokenizer_id=self._settings.tokenizer_id or self._settings.model_id,
            configured_revision=self._settings.tokenizer_revision,
        )

    def count_tokens(self, text: str, *, include_special_tokens: bool) -> int:
        """Count the exact string without adding padding or truncating it."""
        if not isinstance(text, str):
            raise TypeError("Tokenizer input must be a string")
        if not isinstance(include_special_tokens, bool):
            raise TypeError("include_special_tokens must be a boolean")
        loaded = self._ensure_loaded()
        return len(
            loaded.engine.encode(
                text,
                add_special_tokens=include_special_tokens,
            ).ids
        )

    def _ensure_loaded(self) -> LoadedTokenizer:
        if self._loaded is not None:
            return self._loaded
        with self._load_lock:
            if self._loaded is None:
                try:
                    loaded = self._loader(self._settings)
                    loaded.engine.no_padding()
                    loaded.engine.no_truncation()
                except TokenizerLoadError:
                    raise
                except Exception as exc:
                    raise TokenizerLoadError(
                        "Tokenizer initialization failed; check the configured ID, "
                        "revision, backend, and cached artifacts."
                    ) from exc
                self._loaded = loaded
        return self._loaded


def _load_huggingface_tokenizer(settings: EmbeddingSettings) -> LoadedTokenizer:
    """Resolve tokenizer files through Hub cache, then load tokenizer.json only."""
    try:
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise TokenizerLoadError(
            "Tokenizer dependencies are unavailable; install the project's declared "
            "huggingface-hub and tokenizers dependencies."
        ) from exc

    tokenizer_id = settings.tokenizer_id or settings.model_id
    revision = settings.tokenizer_revision
    download_options = {
        "revision": revision,
        "cache_dir": settings.tokenizer_cache_dir,
        "local_files_only": settings.tokenizer_local_files_only,
    }
    try:
        tokenizer_path = Path(
            hf_hub_download(
                repo_id=tokenizer_id,
                filename="tokenizer.json",
                **download_options,
            )
        )
    except Exception as exc:
        if settings.tokenizer_local_files_only:
            message = (
                f"Tokenizer files for {tokenizer_id!r} at {revision or 'main'!r} "
                "are not available in the local Hub cache; populate the cache or "
                "disable tokenizer_local_files_only."
            )
        else:
            message = (
                f"Could not resolve tokenizer files for {tokenizer_id!r} at "
                f"{revision or 'main'!r}; check network access, repository ID, and revision."
            )
        raise TokenizerArtifactsUnavailable(message) from exc

    try:
        engine = Tokenizer.from_file(str(tokenizer_path))
        vocabulary_size = engine.get_vocab_size(with_added_tokens=True)
    except Exception as exc:
        raise TokenizerLoadError(
            f"Tokenizer JSON for {tokenizer_id!r} could not be loaded; verify the selected artifact."
        ) from exc

    resolved_revision = _resolved_revision(tokenizer_path, revision)
    metadata_revision = resolved_revision or revision
    capacity, capacity_status = _read_model_input_capacity(
        hf_hub_download,
        tokenizer_id=tokenizer_id,
        revision=metadata_revision,
        cache_dir=settings.tokenizer_cache_dir,
        local_files_only=settings.tokenizer_local_files_only,
    )
    return LoadedTokenizer(
        engine=engine,
        identity=TokenizerIdentity(
            backend=settings.tokenizer_backend,
            tokenizer_id=tokenizer_id,
            configured_revision=revision,
            resolved_revision=resolved_revision,
            vocabulary_size=vocabulary_size,
            model_input_capacity=capacity,
            capacity_status=capacity_status,
        ),
    )


def _resolved_revision(
    tokenizer_path: Path, configured_revision: str | None
) -> str | None:
    snapshot_revision = tokenizer_path.parent.name
    if re.fullmatch(r"[0-9a-f]{40,64}", snapshot_revision):
        return snapshot_revision
    if configured_revision and re.fullmatch(r"[0-9a-f]{40,64}", configured_revision):
        return configured_revision
    return None


def _read_model_input_capacity(
    hf_hub_download: Callable[..., str],
    *,
    tokenizer_id: str,
    revision: str | None,
    cache_dir: str | None,
    local_files_only: bool,
) -> tuple[int | None, CapacityStatus]:
    """Read model_max_length metadata without treating sentinels as capacities."""
    try:
        path = hf_hub_download(
            repo_id=tokenizer_id,
            filename="tokenizer_config.json",
            revision=revision,
            cache_dir=cache_dir,
            local_files_only=local_files_only,
        )
        with Path(path).open(encoding="utf-8") as metadata_file:
            raw_value = json.load(metadata_file).get("model_max_length")
    except Exception:  # noqa: BLE001 -- capacity metadata is optional and best-effort.
        return None, "unavailable"

    if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value <= 0:
        return None, "invalid"
    if raw_value >= MAX_LENGTH_SENTINEL:
        return None, "sentinel"
    return raw_value, "known"
