"""Real graphs, artifacts, SQLite catalog and embedded Qdrant; explicit test model doubles."""

import json
from types import SimpleNamespace

import pytest
from apps.core.observability import PipelineTrace
from apps.document_ingestion.workflows.document_ingestion.state import initial_state
from apps.orchestration.errors import WorkflowFailed
from apps.orchestration.execution import PipelineRunner
from apps.orchestration.graph_runtime import GraphRunOptions
from apps.pipelines.runtime import build_pipelines
from apps.retrieval.workflows.answer.state import initial_state as query_state
from langgraph.checkpoint.memory import InMemorySaver
from packages.contracts.access import AccessMetadata, TrustedAccessContext
from packages.contracts.answering import AnswerResponse, Citation
from packages.contracts.common import ContentRef, SourceRef, SourceVersion
from packages.contracts.document import DocumentInput
from packages.contracts.retrieval import SearchRequest
from packages.documents.normalization.service import PersianNormalizer
from packages.knowledge.configuration import KnowledgeConfiguration
from packages.knowledge.publication.catalog import LocalSqliteGenerationCatalog
from packages.storage import service as storage
from packages.storage.artifacts.repository import LocalArtifactRepository
from packages.storage.qdrant.adapter import QdrantAdapter
from qdrant_client import QdrantClient, models


class TestEmbedding:
    """Test double, not a real embedding model; deterministic nonzero four-vector."""

    __test__ = False
    calls = 0
    fail = False

    async def embed_texts(self, texts, *, model_id):
        self.calls += 1
        if self.fail:
            raise ConnectionError("TEST-PRIVATE-provider-detail")
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class Authorization:
    denied = False

    async def authorize_sources(self, context, sources):
        return [] if self.denied else sources


class TestGenerator:
    __test__ = False
    calls = 0
    invalid = False

    async def generate(self, request):
        self.calls += 1
        item = request.evidence[0]
        return AnswerResponse(
            answer="Answer grounded in the fixture.",
            status="completed",
            citations=[
                Citation(
                    evidence_id="invented" if self.invalid else item.evidence_id,
                    source=item.source,
                    location=item.location,
                )
            ],
        )


@pytest.fixture
def env(tmp_path, monkeypatch):
    client = QdrantClient(":memory:")
    client.create_collection(
        "pipeline_test",
        vectors_config={
            "dense": models.VectorParams(size=4, distance=models.Distance.COSINE)
        },
    )
    client.create_payload_index(
        "pipeline_test",
        "text",
        models.TextIndexParams(
            type="text",
            tokenizer=models.TokenizerType.WORD,
            scoring=models.TextScoringParams(type=models.TextScoringType.BM25),
        ),
    )
    config = storage.StorageConfig(
        collection_name="pipeline_test", vector_size=4, max_retries=0
    )
    monkeypatch.setattr(
        storage, "_adapter", lambda _: QdrantAdapter(config, client=client)
    )
    source = SourceVersion(
        source=SourceRef(
            source_id="source-1", knowledge_space_id="demo", source_type="document"
        ),
        version="1",
    )
    access = AccessMetadata(tenant_id="test", acl_principals=["user:1"])
    context = TrustedAccessContext(
        subject_id="1", tenant_id="test", principals=["user:1"]
    )
    configuration = KnowledgeConfiguration(
        embedding={"model_id": "TEST-ONLY", "dimensions": 4}
    )
    artifacts = LocalArtifactRepository(
        root=tmp_path / "artifacts",
        allowed_roots=[tmp_path],
        max_raw_bytes=10000,
        tenant_id="test",
    )
    catalog = LocalSqliteGenerationCatalog(database_path=tmp_path / "catalog.sqlite")
    auth, embeddings, generator = Authorization(), TestEmbedding(), TestGenerator()

    def build(checkpointer=None, **kwargs):
        return build_pipelines(
            configuration=configuration,
            artifacts=artifacts,
            catalog=catalog,
            storage_config=config,
            authorization=auth,
            count_tokens=lambda t: len(t.split()),
            embedding_provider=embeddings,
            embed_query=lambda _: [1.0, 0.0, 0.0, 0.0],
            query_normalizer=PersianNormalizer,
            checkpointer=checkpointer or InMemorySaver(),
            generator=generator,
            **kwargs,
        )

    raw = tmp_path / "document.txt"
    raw.write_text("Private fixture alpha.\n\nSecond paragraph.", encoding="utf-8")
    document = DocumentInput(source=source, content=ContentRef(uri=raw.as_uri()))
    state = initial_state(document, filename=raw.name, content_type="text/plain")
    yield SimpleNamespace(**locals())
    client.close()


async def run(env, graph, state, name, access=None, resume=False):
    return await PipelineRunner().run(
        graph,
        state,
        options=GraphRunOptions(
            thread_id=name, context={"access": access or env.access}, resume=resume
        ),
        trace=PipelineTrace(env.tmp_path / f"{name}.jsonl", run_id=name, workflow=name),
    )


@pytest.mark.asyncio
async def test_ingest_retrieve_and_grounded_answer(env):
    runtime = env.build()
    stored = await run(env, runtime.ingestion, env.state, "ingestion")
    assert (
        stored["published"]
        and stored["index_validated"]
        and stored["indexed_count"] == 1
    )
    assert env.client.count("pipeline_test", exact=True).count == 1
    result = await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture", mode="semantic"), generate=True),
        "retrieval",
        env.context,
    )
    assert result["status"] == "completed"
    assert (
        result["answer"]["citations"][0]["evidence_id"]
        == result["evidence"][0]["evidence_id"]
    )
    trace = (env.tmp_path / "ingestion.jsonl").read_text()
    assert "Private fixture" not in trace and "TEST-ONLY" not in trace
    events = [json.loads(line) for line in trace.splitlines()]
    assert len([e for e in events if e["event"] == "node_started"]) == 7
    assert any(e["event"] == "checkpoint" for e in events)
    assert (env.tmp_path / "retrieval.html").exists()


@pytest.mark.asyncio
async def test_sqlite_pause_resume_survives_new_graph_and_connection(env):
    from apps.orchestration.checkpointer import CheckpointerFactory, CheckpointSettings

    settings = CheckpointSettings(
        backend="sqlite", sqlite_path=env.tmp_path / "checkpoints.sqlite"
    )
    async with CheckpointerFactory(settings).open() as saver:
        runtime = env.build(saver, ingestion_breakpoints=("parse",))
        state = await run(env, runtime.ingestion, env.state, "paused")
        assert state["last_step"] == "parse" and env.embeddings.calls == 0
        env.raw.unlink()
    async with CheckpointerFactory(settings).open() as saver:
        runtime = env.build(saver)
        state = await run(env, runtime.ingestion, None, "paused", resume=True)
        assert state["published"] and env.embeddings.calls == 1


@pytest.mark.asyncio
async def test_provider_failure_is_traced_and_resumable(env):
    runtime = env.build()
    env.embeddings.fail = True
    with pytest.raises(WorkflowFailed):
        await run(env, runtime.ingestion, env.state, "failed")
    assert env.client.count("pipeline_test").count == 0
    assert "TEST-PRIVATE" not in (env.tmp_path / "failed.jsonl").read_text()
    env.embeddings.fail = False
    state = await run(env, runtime.ingestion, None, "failed", resume=True)
    assert state["published"]


@pytest.mark.asyncio
async def test_unauthorized_or_unpublished_evidence_never_reaches_model(env):
    runtime = env.build()
    empty = await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture"), generate=True),
        "before",
        env.context,
    )
    assert empty["answer"]["status"] == "no_evidence" and env.generator.calls == 0
    await run(env, runtime.ingestion, env.state, "ingest")
    env.auth.denied = True
    denied = await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture"), generate=True),
        "denied",
        env.context,
    )
    assert denied["evidence"] == [] and env.generator.calls == 0


@pytest.mark.asyncio
async def test_other_tenant_and_explicit_empty_source_filter(env):
    runtime = env.build()
    await run(env, runtime.ingestion, env.state, "ingest")
    other = env.context.model_copy(update={"tenant_id": "other"})
    result = await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture")),
        "other",
        other,
    )
    assert not result["evidence"]
    result = await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture", source_ids=[])),
        "empty-filter",
        env.context,
    )
    assert not result["evidence"]


@pytest.mark.asyncio
async def test_resume_rejects_changed_identity(env):
    runtime = env.build(retrieval_breakpoints=("prefilter",))
    await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture")),
        "owner",
        env.context,
    )
    with pytest.raises(WorkflowFailed) as exc:
        await run(
            env,
            runtime.retrieval,
            None,
            "owner",
            env.context.model_copy(update={"subject_id": "attacker"}),
            resume=True,
        )
    assert exc.value.error_code.value == "access_denied"


@pytest.mark.asyncio
async def test_repeat_ingestion_does_not_duplicate_points(env):
    runtime = env.build()
    a = await run(env, runtime.ingestion, env.state, "first")
    b = await run(env, runtime.ingestion, env.state, "second")
    assert a["generation_id"] == b["generation_id"]
    assert env.client.count("pipeline_test", exact=True).count == 1


@pytest.mark.asyncio
async def test_invalid_citation_fails(env):
    runtime = env.build()
    await run(env, runtime.ingestion, env.state, "ingest")
    env.generator.invalid = True
    with pytest.raises(WorkflowFailed):
        await run(
            env,
            runtime.retrieval,
            query_state(SearchRequest(query="fixture"), generate=True),
            "bad-answer",
            env.context,
        )


@pytest.mark.asyncio
async def test_mime_alias_and_missing_binary_parser(env):
    runtime = env.build()
    state = {**env.state, "content_type": "application/octet-stream"}
    assert (await run(env, runtime.ingestion, state, "octet"))["published"]
    with pytest.raises(WorkflowFailed) as exc:
        await run(
            env,
            runtime.ingestion,
            {
                **env.state,
                "filename": "document.pdf",
                "content_type": "application/pdf",
            },
            "pdf",
        )
    assert exc.value.error_code.value == "unsupported_format"


@pytest.mark.asyncio
async def test_tiny_context_budget_skips_generation(env):
    runtime = env.build(max_context_tokens=1)
    await run(env, runtime.ingestion, env.state, "ingest")
    result = await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture"), generate=True),
        "budget",
        env.context,
    )
    assert result["answer"]["status"] == "no_evidence" and env.generator.calls == 0


@pytest.mark.asyncio
async def test_trace_disk_error_does_not_change_processing(env):
    runtime = env.build()
    trace_path = env.tmp_path / "directory-not-a-file"
    trace_path.mkdir()
    trace = PipelineTrace(trace_path, run_id="trace-error", workflow="ingestion")
    result = await PipelineRunner().run(
        runtime.ingestion,
        env.state,
        options=GraphRunOptions(
            thread_id="trace-error", context={"access": env.access}
        ),
        trace=trace,
    )
    assert result["published"] and trace.error == "local_trace_unavailable"


@pytest.mark.asyncio
async def test_revoked_permission_after_checkpoint_stops_answer(env):
    runtime = env.build(retrieval_breakpoints=("retrieve",))
    await run(env, runtime.ingestion, env.state, "ingest")
    state = await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture", mode="semantic"), generate=True),
        "revoked",
        env.context,
    )
    assert state["results"]
    env.auth.denied = True
    # Rebuild without a breakpoint, preserving the same saver.
    state = await run(env, runtime.retrieval, None, "revoked", env.context, resume=True)
    assert state["evidence"] == [] and env.generator.calls == 0


@pytest.mark.asyncio
async def test_only_current_generation_is_retrieved(env):
    runtime = env.build()
    old = await run(env, runtime.ingestion, env.state, "version-1")
    new_source = env.source.model_copy(update={"version": "2"})
    new_state = {**env.state, "source": new_source.model_dump(mode="json")}
    new = await run(env, runtime.ingestion, new_state, "version-2")
    assert old["generation_id"] != new["generation_id"]
    result = await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture", mode="semantic")),
        "latest",
        env.context,
    )
    assert result["evidence"] and {r["generation_id"] for r in result["evidence"]} == {
        new["generation_id"]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["semantic", "keyword", "hybrid"])
async def test_all_search_modes(env, mode):
    runtime = env.build()
    await run(env, runtime.ingestion, env.state, "ingest")
    result = await run(
        env,
        runtime.retrieval,
        query_state(SearchRequest(query="fixture", mode=mode)),
        "mode",
        env.context,
    )
    assert result["evidence"] and result["evidence"][0]["retrieval_method"] == mode


def test_cli_pause_inspect_resume_and_query_across_processes(tmp_path):
    import re
    import subprocess
    import sys
    from pathlib import Path

    project = Path(__file__).resolve().parents[2]
    raw = tmp_path / "sample.txt"
    raw.write_text("CLI private fixture.", encoding="utf-8")
    common = [
        sys.executable,
        "-m",
        "apps.pipelines.cli",
        "--work-dir",
        str(tmp_path / "run"),
        "--factory",
        "test.workflows.cli_fixture:build",
        "--local-access",
    ]

    def call(args):
        completed = subprocess.run(
            common + args,
            check=False,
            cwd=project,
            text=True,
            capture_output=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return completed.stdout

    output = call(
        [
            "--pause-after",
            "parse",
            "ingest",
            str(raw),
            "--source-id",
            "cli-source",
            "--space",
            "demo",
        ]
    )
    run_id = re.search(r"run_id=(ingestion-[\w-]+)", output).group(1)
    assert "paused" in output
    inspect_output = call(["inspect", run_id, "--history"])
    assert (
        "checkpoint_id" in inspect_output
        and "CLI private fixture" not in inspect_output
    )
    output = call(["resume", run_id, "--workflow", "ingestion"])
    assert '"published": true' in output
    output = call(["query", "fixture", "--mode", "semantic"])
    assert "CLI private fixture" in output
    trace = (tmp_path / "run" / "traces" / f"{run_id}.html").read_text()
    assert "resumed" in trace and "CLI private fixture" not in trace
