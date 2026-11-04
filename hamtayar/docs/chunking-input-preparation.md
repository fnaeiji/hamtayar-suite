# Chunking configuration and input preparation

## Configuration

Edit [`config/knowledge.toml`](../config/knowledge.toml). It keeps the `[chunking]`
and `[embedding]` settings together. Precedence is **model defaults → TOML →
existing application environment overrides**. `HAMTAYAR_KNOWLEDGE_CONFIG_PATH`
selects the file, and the existing `HAMTAYAR_EMBEDDING_MODEL` overrides
`embedding.model_id`; there are no chunking environment overrides. The app
composition helper is `apps.core.config.load_knowledge_settings`. Other hosts
can call `packages.knowledge.service.load_configuration` with a path and
explicit overrides. Loading is on demand; importing Knowledge performs no
configuration-file, environment, model, or network I/O.

Initial settings are strategy/profile `structure_aware` /
`structure_aware_v1`, `max_tokens=512`, zero overlap, and error on oversized
content. `max_tokens` is an initial budget, not a model's maximum input length.
The tokenizer counter measures exactly the supplied string; a future chunker
must pass the final text sent for embedding, including any added text and
special tokens.

The selected model is `BAAI/bge-m3`; expected output is dense, 1024-dimensional,
and normalized. The checked-in file pins the model and same-repository tokenizer
to revision `5617a9f61b028005a4858fdac845db406aefb181`. Tokenizer ID defaults to
the effective model ID after overrides. A model revision is inherited only
when the tokenizer ID is the same repository and no tokenizer revision was
supplied. For another tokenizer repository, its revision remains unset unless
explicitly provided. Blank revisions are rejected. Application model overrides
clear a file revision tied to another model repository. An explicitly selected
tokenizer must be verified to match the embedding model's tokenizer before
production use. A changed identifier alone does not establish compatibility;
changing `dimensions` does not promise arbitrary vector truncation.

The only supported backend is `huggingface_tokenizers`. Its adapter lazily
loads `tokenizer.json` through Hugging Face Hub, disables padding and
truncation, and reuses the tokenizer instance. It loads no embedding weights
and executes no remote custom code. `tokenizer_cache_dir` is optional;
`tokenizer_local_files_only=true` enables offline/cache-only operation. The
checked-in setting permits Hub resolution on first use. The BGE tokenizer
[metadata at the pinned revision](https://huggingface.co/BAAI/bge-m3/blob/5617a9f61b028005a4858fdac845db406aefb181/tokenizer_config.json)
reports an 8192-token input capacity; this is distinct from the
configurable 512-token chunk budget. Missing or sentinel capacity metadata is
reported as unresolved, never guessed. The loader cannot prove the compatibility
of separately configured model and tokenizer artifacts.

## Prepared input API

Call `packages.knowledge.service.prepare_chunking_request(document, *, access,
configuration)`. It accepts a processed `ParsedDocument`, explicit trusted
`AccessMetadata`, and validated `KnowledgeConfiguration`, then returns the
shared `ChunkingRequest` with `kind="document"`. It rejects repository sources.

Each document block maps to one item in original order. The item receives
`block.effective_text` exactly, including empty strings and whitespace;
source/version, location, block ID/type, heading level, code language, and
protected spans are preserved. Missing IDs and locations remain missing.
Locations still address the original decoded source. Protected spans remain
zero-based Python code-point ranges with end-exclusive bounds into the item
text. The request uses `configuration.chunking.profile` as `processing_profile`;
this string does not snapshot `max_tokens`, embedding settings, or other
configuration. The caller passes the same validated configuration explicitly
to future chunking operations.

The mapper does not clean, normalize, trim, split, merge, tokenize, or reparse.
It does not duplicate `original_content` or document processing metadata into
the request; parser, cleaning, and normalization provenance stays on the
`ParsedDocument` for orchestration to retain. It does not create block IDs. A
downstream consumer that requires IDs must ensure parsers or an earlier
identity-owning stage supply unique IDs before relying on them.

### Access boundary

`IngestionRequest.access`, `ChunkingRequest.access`, and `Chunk.access` use the
same required `AccessMetadata` contract (`tenant_id`, `acl_principals`). Access
is not stored on `ParsedDocument`. Orchestration must pass the trusted access
metadata associated with the same source, normally from
`IngestionRequest.access`. Preparation copies its values unchanged and does
not infer tenant or ACL values. This boundary validates representation; a
Pydantic model by itself does not authenticate its origin. Future chunk
production must propagate request access into each output `Chunk`.

## Tokenizer API and counting semantics

`packages.knowledge.service.create_tokenizer(configuration)` creates a lazy,
reusable adapter. `count_tokens(text, configuration=...)` counts the exact
string, and `count_prepared_request(request, configuration=...)` returns
ordered per-item diagnostics. Callers can inject a `TokenCounter` for isolated
tests. Configuration stays explicit; loading it does not load tokenizer
artifacts. The configured `include_special_tokens` policy is passed explicitly
to the backend. Empty text has zero content tokens when special tokens are
excluded; when included, the tokenizer may return special-token IDs. Whitespace
and all other code points are passed unchanged. Long text is fully counted with
truncation disabled.

Per-item counts are diagnostics, not final chunks, and their sum is not a count
of concatenated text. Future chunking must count the exact final embedding
input, including any headings, separators, prefixes, and special tokens.
Protected-span offsets remain code-point offsets, not token offsets. A block
over budget is normal input for a later splitter. The 512-token setting is a
configured chunk budget, not a tokenizer/model input limit.

## Shared input-contract compatibility

The authorized changes to `packages/contracts/chunks.py` add optional
`block_id`, `block_type`, `heading_level`, `code_language`, and
`protected_spans` fields to `ChunkingItem`. `DocumentBlockType` is shared from
the document contract, and spans reuse `ProtectedSpan`. Validators enforce
heading/code metadata consistency, span bounds/order, and unique non-null
document block IDs within a request. `protected_spans` receives a fresh list
per item. Existing code-content callers can omit all document structure and
retain `symbol_id` behavior.

`ChunkingItem.text` now accepts `""`, and `ChunkingRequest.items` accepts an
empty list for an empty document. Access remains required. `Chunk.text` remains
nonempty; `Chunk`, `ChunkingResult`, embeddings, indexing, and storage
contracts are unchanged. New contract defaults let old serialized requests
without structural fields load in the new version. The reverse direction is
not fully compatible: because old contracts forbid extra fields, old consumers
reject newly serialized items containing the added fields. Old consumers also
reject empty item text or an empty request. Before rolling back with prepared
requests in flight, stop/discard that transient preparation traffic and restore
the previous schema/validators; no chunk or index output depends on the added
fields.

## Review samples

Run the exporter to regenerate both processed-document samples and prepared
request samples. To additionally count prepared items (which can resolve or
download tokenizer artifacts unless local-only mode is set), run with
`--with-token-counts`:

```powershell
.venv\Scripts\python.exe scripts\export_document_samples.py
.venv\Scripts\python.exe scripts\export_document_samples.py --with-token-counts
.venv\Scripts\python.exe -m pytest test\unit\knowledge test\integration\test_chunking_input_preparation.py
.venv\Scripts\python.exe -m pytest test\integration\test_bge_m3_tokenizer.py
.venv\Scripts\python.exe -m pytest test\packages\contracts\test_chunks.py test\packages\contracts\test_contract_flow.py
.venv\Scripts\python.exe -m ruff check packages\contracts\chunks.py packages\contracts\document.py packages\knowledge apps\core\config.py scripts\export_document_samples.py test\unit\knowledge test\integration\test_chunking_input_preparation.py
git diff --check
```

The generated `test/outputs/documents/sample_markdown_chunking_request.json`
and `sample_txt_chunking_request.json` are **prepared inputs**, not chunking
outputs. They contain synthetic review access values, not production ACLs.
The optional `sample_chunking_token_counts.json` artifact reports tokenizer
identity/revision, special-token policy, chunk budget, and each item's order,
block ID/type, count, and over-budget flag. It is explicitly per-item
diagnostic output; it is not chunking output and item counts must not be summed
to estimate tokenization of concatenated text.

For offline integration verification, first cache the pinned tokenizer
artifacts, then set `tokenizer_local_files_only=true` (or invoke the BGE test,
which forces that setting). The real-tokenizer test skips explicitly if the
`tokenizers` package or pinned files are unavailable. It compares counts with
direct tokenization of the same cached artifact. The checked-in model revision
is currently pinned; an application override that changes the repository
clears that revision and therefore remains unpinned until the operator selects
an immutable revision.

## Remaining work

This task counts exact strings but does not split or merge text, choose
boundaries, apply overlap, generate chunk IDs, run embedding inference, or use
storage. The next chunking task can consume prepared requests and this tokenizer
counter; it must still define its exact embedding input and split policy.
