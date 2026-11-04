import json

import pytest

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import ChunkingItem, ChunkingRequest
from packages.contracts.common import SourceRef, SourceVersion
from packages.knowledge.chunking.token_counting import count_chunking_request_items
from packages.knowledge.configuration import (
    ChunkingSettings,
    EmbeddingSettings,
    KnowledgeConfiguration,
)
from packages.knowledge.service import (
    count_prepared_request,
    count_tokens,
    create_tokenizer,
)
from packages.knowledge.tokenizer import (
    MAX_LENGTH_SENTINEL,
    HuggingFaceTokenizer,
    LoadedTokenizer,
    TokenizerArtifactsUnavailable,
    TokenizerIdentity,
    _read_model_input_capacity,
)


class _Encoding:
    def __init__(self, ids):
        self.ids = ids


class _Engine:
    def __init__(self):
        self.padding_disabled = 0
        self.truncation_disabled = 0
        self.calls = []

    def no_padding(self):
        self.padding_disabled += 1

    def no_truncation(self):
        self.truncation_disabled += 1

    def encode(self, text, *, add_special_tokens=True):
        self.calls.append((text, add_special_tokens))
        content_count = len(text.encode("utf-8"))
        return _Encoding([0] * (content_count + (2 if add_special_tokens else 0)))

    def get_vocab_size(self, with_added_tokens=True):
        return 123


def _identity(capacity=8192, capacity_status="known"):
    return TokenizerIdentity(
        backend="huggingface_tokenizers",
        tokenizer_id="example/model",
        configured_revision="a" * 40,
        resolved_revision="a" * 40,
        vocabulary_size=123,
        model_input_capacity=capacity,
        capacity_status=capacity_status,
    )


def _configuration(**chunking_overrides):
    return KnowledgeConfiguration(
        chunking=ChunkingSettings(**chunking_overrides),
        embedding=EmbeddingSettings(model_id="example/model"),
    )


def test_tokenizer_is_lazy_reused_and_explicitly_disables_padding_and_truncation():
    engine = _Engine()
    loader_calls = []

    def load(settings):
        loader_calls.append(settings)
        return LoadedTokenizer(engine, _identity())

    tokenizer = HuggingFaceTokenizer(
        EmbeddingSettings(model_id="example/model"), loader=load
    )

    assert loader_calls == []
    assert (
        tokenizer.count_tokens("  hi  ", include_special_tokens=True)
        == len(b"  hi  ") + 2
    )
    assert tokenizer.count_tokens("", include_special_tokens=False) == 0
    assert len(loader_calls) == 1
    assert engine.padding_disabled == 1
    assert engine.truncation_disabled == 1
    assert engine.calls == [("  hi  ", True), ("", False)]
    assert tokenizer.identity.resolved_revision == "a" * 40


def test_empty_and_whitespace_counting_is_explicit_and_does_not_strip_input():
    engine = _Engine()
    tokenizer = HuggingFaceTokenizer(
        EmbeddingSettings(model_id="example/model"),
        loader=lambda _settings: LoadedTokenizer(engine, _identity()),
    )

    assert tokenizer.count_tokens("", include_special_tokens=False) == 0
    assert tokenizer.count_tokens("", include_special_tokens=True) == 2
    assert tokenizer.count_tokens(" \t ", include_special_tokens=False) == 3
    assert engine.calls == [("", False), ("", True), (" \t ", False)]


def test_tokenizer_rejects_non_string_text_and_non_boolean_special_policy():
    tokenizer = HuggingFaceTokenizer(
        EmbeddingSettings(model_id="example/model"),
        loader=lambda _settings: LoadedTokenizer(_Engine(), _identity()),
    )

    with pytest.raises(TypeError, match="input must be a string"):
        tokenizer.count_tokens(7, include_special_tokens=True)
    with pytest.raises(TypeError, match="must be a boolean"):
        tokenizer.count_tokens("text", include_special_tokens=1)


def test_artifact_load_error_is_actionable_and_not_silently_replaced():
    def fail(_settings):
        raise TokenizerArtifactsUnavailable("No cached tokenizer artifacts")

    tokenizer = HuggingFaceTokenizer(
        EmbeddingSettings(model_id="example/model"), loader=fail
    )

    with pytest.raises(
        TokenizerArtifactsUnavailable, match="No cached tokenizer artifacts"
    ):
        tokenizer.count_tokens("text", include_special_tokens=True)


def test_tokenizer_capacity_metadata_distinguishes_known_missing_and_sentinel(tmp_path):
    metadata = tmp_path / "tokenizer_config.json"

    def fetch(value):
        metadata.write_text(json.dumps({"model_max_length": value}), encoding="utf-8")
        return str(metadata)

    capacity, status = _read_model_input_capacity(
        lambda **_kwargs: fetch(8192),
        tokenizer_id="example/model",
        revision="a" * 40,
        cache_dir=None,
        local_files_only=True,
    )
    assert (capacity, status) == (8192, "known")

    capacity, status = _read_model_input_capacity(
        lambda **_kwargs: fetch(MAX_LENGTH_SENTINEL),
        tokenizer_id="example/model",
        revision="a" * 40,
        cache_dir=None,
        local_files_only=True,
    )
    assert (capacity, status) == (None, "sentinel")

    capacity, status = _read_model_input_capacity(
        lambda **_kwargs: (_ for _ in ()).throw(FileNotFoundError()),
        tokenizer_id="example/model",
        revision="a" * 40,
        cache_dir=None,
        local_files_only=True,
    )
    assert (capacity, status) == (None, "unavailable")


class _CountingFake:
    def __init__(self, *, capacity=8192):
        self.identity = _identity(capacity=capacity)
        self.calls = []

    def count_tokens(self, text, *, include_special_tokens):
        self.calls.append((text, include_special_tokens))
        return len(text) + int(include_special_tokens)


def _request(items):
    return ChunkingRequest(
        source=SourceVersion(
            source=SourceRef(
                source_id="doc-1",
                knowledge_space_id="space-1",
                source_type="document",
            ),
            version="v1",
        ),
        kind="document",
        items=items,
        access=AccessMetadata(tenant_id="tenant", acl_principals=["reader"]),
    )


def test_prepared_items_are_counted_in_order_without_request_mutation():
    request = _request(
        [
            ChunkingItem(text="one", block_id="block-1", block_type="paragraph"),
            ChunkingItem(text="", block_id="block-2", block_type="paragraph"),
            ChunkingItem(text="  three  ", block_id="block-3", block_type="code"),
        ]
    )
    before = request.model_dump(mode="json")
    config = _configuration(max_tokens=5)
    fake = _CountingFake()

    report = count_prepared_request(request, configuration=config, tokenizer=fake)

    assert [item.order for item in report.items] == [1, 2, 3]
    assert [item.block_id for item in report.items] == ["block-1", "block-2", "block-3"]
    assert [item.token_count for item in report.items] == [4, 1, 10]
    assert [item.exceeds_chunk_budget for item in report.items] == [False, False, True]
    assert all(call[1] is True for call in fake.calls)
    assert [call[0] for call in fake.calls] == ["one", "", "  three  "]
    assert request.model_dump(mode="json") == before


def test_empty_request_needs_no_tokenizer_load_and_returns_no_item_counts():
    request = _request([])
    fake = _CountingFake()

    report = count_chunking_request_items(
        request,
        configuration=_configuration(),
        tokenizer=fake,
    )

    assert report.items == ()
    assert fake.calls == []


def test_configured_budget_is_checked_against_known_capacity():
    request = _request([ChunkingItem(text="short")])
    fake = _CountingFake(capacity=4)

    with pytest.raises(
        ValueError, match="exceeds the tokenizer-reported model input capacity"
    ):
        count_chunking_request_items(
            request,
            configuration=_configuration(max_tokens=5),
            tokenizer=fake,
        )


def test_create_tokenizer_and_count_tokens_keep_loading_lazy():
    configuration = _configuration()
    tokenizer = create_tokenizer(configuration)

    assert tokenizer.identity.tokenizer_id == "example/model"
    # Counting is the first operation that asks the adapter to load artifacts.
    # An injected instance can be used when artifacts should not be touched.
    fake = _CountingFake()
    assert count_tokens("x", configuration=configuration, tokenizer=fake) == 2


def test_service_count_tokens_rejects_non_string_before_calling_injected_counter():
    fake = _CountingFake()

    with pytest.raises(TypeError, match="input must be a string"):
        count_tokens(3, configuration=_configuration(), tokenizer=fake)

    assert fake.calls == []
