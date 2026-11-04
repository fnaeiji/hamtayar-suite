"""Real, offline-only verification of the configured BGE-M3 tokenizer files."""

import pytest

from packages.contracts.access import AccessMetadata
from packages.contracts.common import SourceRef, SourceVersion
from packages.contracts.document import DocumentBlock, ParsedDocument, ProtectedSpan
from packages.knowledge.service import (
    count_prepared_request,
    create_tokenizer,
    load_configuration,
    prepare_chunking_request,
)
from packages.knowledge.tokenizer import TokenizerArtifactsUnavailable

EXPECTED_BGE_M3_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"


@pytest.fixture(scope="module")
def bge_tokenizer():
    pytest.importorskip("tokenizers", reason="install the locked tokenizers dependency")
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    configuration = load_configuration(
        overrides={"embedding": {"tokenizer_local_files_only": True}}
    )
    tokenizer = create_tokenizer(configuration)
    try:
        tokenizer.count_tokens("warm-up", include_special_tokens=True)
    except TokenizerArtifactsUnavailable as exc:
        pytest.skip(f"BGE-M3 tokenizer artifacts are not cached locally: {exc}")

    identity = tokenizer.identity
    assert identity.tokenizer_id == "BAAI/bge-m3"
    assert identity.configured_revision == EXPECTED_BGE_M3_REVISION
    assert identity.resolved_revision == EXPECTED_BGE_M3_REVISION
    artifact = hf_hub_download(
        repo_id=identity.tokenizer_id,
        filename="tokenizer.json",
        revision=identity.resolved_revision,
        cache_dir=configuration.embedding.tokenizer_cache_dir,
        local_files_only=True,
    )
    direct = Tokenizer.from_file(artifact)
    direct.no_padding()
    direct.no_truncation()
    return configuration, tokenizer, direct


def _prepared_samples(configuration):
    url_text = "Visit https://example.com/path?q=1 now"
    url = "https://example.com/path?q=1"
    start = url_text.index(url)
    long_text = "long tokenizer input " * 700
    source = SourceVersion(
        source=SourceRef(
            source_id="bge-tokenizer-samples",
            knowledge_space_id="tokenizer-integration",
            source_type="document",
        ),
        version="v1",
    )
    document = ParsedDocument(
        source=source,
        blocks=[
            DocumentBlock(block_type="paragraph", text="سامانه‌ی پایش اسناد"),
            DocumentBlock(block_type="paragraph", text="An English tokenizer sample."),
            DocumentBlock(block_type="paragraph", text="Mixed text برای retrieval."),
            DocumentBlock(block_type="paragraph", text="Emoji 👩‍💻 and ZWNJ می‌روم."),
            DocumentBlock(
                block_type="code",
                text="def f(value):\n    return value + 1",
                code_language="python",
            ),
            DocumentBlock(
                block_type="paragraph",
                text=url_text,
                protected_spans=[
                    ProtectedSpan(start=start, end=start + len(url), kind="url")
                ],
            ),
            DocumentBlock(
                block_type="table",
                text="| field | مقدار |\n| --- | --- |\n| name | value |",
            ),
            DocumentBlock(block_type="paragraph", text=long_text),
        ],
    )
    access = AccessMetadata(
        tenant_id="tokenizer-test-tenant",
        acl_principals=["tokenizer-test-reader"],
    )
    return (
        prepare_chunking_request(
            document,
            access=access,
            configuration=configuration,
        ),
        long_text,
    )


def test_bge_m3_counts_real_persian_english_code_url_and_table_tokens(bge_tokenizer):
    configuration, tokenizer, direct = bge_tokenizer
    request, long_text = _prepared_samples(configuration)
    before = request.model_dump(mode="json")
    texts = [item.text for item in request.items]
    report = count_prepared_request(
        request, configuration=configuration, tokenizer=tokenizer
    )

    assert [item.token_count for item in report.items] == [
        len(direct.encode(text, add_special_tokens=True).ids) for text in texts
    ]
    assert tokenizer.count_tokens("", include_special_tokens=False) == 0
    assert tokenizer.count_tokens("", include_special_tokens=True) == len(
        direct.encode("", add_special_tokens=True).ids
    )

    full_long_count = len(direct.encode(long_text, add_special_tokens=True).ids)
    assert report.items[-1].token_count == full_long_count
    assert full_long_count > configuration.chunking.max_tokens
    assert request.model_dump(mode="json") == before

    url_item = request.items[5]
    url_span = url_item.protected_spans[0]
    assert (
        url_item.text[url_span.start : url_span.end] == "https://example.com/path?q=1"
    )

    for text in texts:
        assert tokenizer.count_tokens(text, include_special_tokens=False) == len(
            direct.encode(text, add_special_tokens=False).ids
        )


def test_bge_m3_reports_metadata_capacity_separately_from_chunk_budget(bge_tokenizer):
    configuration, tokenizer, _direct = bge_tokenizer
    identity = tokenizer.identity

    if identity.capacity_status != "known":
        pytest.skip(
            f"BGE-M3 model input capacity metadata is {identity.capacity_status}"
        )

    assert identity.model_input_capacity == 8192
    assert configuration.chunking.max_tokens == 512
    assert identity.model_input_capacity != configuration.chunking.max_tokens
