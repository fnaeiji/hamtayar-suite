"""Run, pause, inspect and resume the graphs without FastAPI."""

import argparse
import asyncio
import importlib
import inspect
import json
from pathlib import Path
from uuid import uuid4

from packages.contracts.common import ContentRef, SourceRef, SourceVersion
from packages.contracts.document import DocumentInput
from packages.contracts.retrieval import SearchRequest

from apps.core.observability import PipelineTrace, state_summary
from apps.document_ingestion.workflows.document_ingestion.state import (
    initial_state as ingestion_state,
)
from apps.orchestration.checkpointer import CheckpointerFactory, CheckpointSettings
from apps.orchestration.execution import PipelineRunner
from apps.orchestration.graph_runtime import GraphRunOptions
from apps.retrieval.workflows.answer.state import initial_state as retrieval_state


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work-dir", default=".runtime/pipelines")
    p.add_argument("--config", default="config/knowledge.toml")
    p.add_argument(
        "--factory",
        help="Trusted runtime factory module:function; receives (args, checkpointer), returns (runtime, verified_context)",
    )
    p.add_argument(
        "--local-access",
        action="store_true",
        help="Explicitly trust this single-user local CLI session; never use for multi-user deployment",
    )
    p.add_argument("--tenant", default="local")
    p.add_argument("--subject", default="local-operator")
    p.add_argument("--principal", action="append")
    p.add_argument("--allowed-root", action="append", default=None)
    p.add_argument("--max-bytes", type=int, default=20 * 1024 * 1024)
    p.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    p.add_argument("--collection", default="hamtayar_search_pipeline")
    p.add_argument("--vector-name", default="dense")
    p.add_argument(
        "--debug", action="store_true", help="Print the local traceback on failure"
    )
    p.add_argument("--timeout", type=float, default=600)
    p.add_argument("--pause-after", action="append", default=[])
    sub = p.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--source-id", required=True)
    ingest.add_argument("--space", required=True)
    ingest.add_argument("--version", default="1")
    ingest.add_argument("--profile", default="default")
    ingest.set_defaults(workflow="ingestion")
    query = sub.add_parser("query")
    query.add_argument("question")
    query.add_argument(
        "--mode", choices=["semantic", "keyword", "hybrid"], default="semantic"
    )
    query.add_argument("--top-k", type=int, default=10)
    query.add_argument("--source-id", action="append")
    query.add_argument("--generate", action="store_true")
    query.set_defaults(workflow="retrieval")
    resume = sub.add_parser("resume")
    resume.add_argument("run_id")
    resume.add_argument("--workflow", choices=["ingestion", "retrieval"], required=True)
    view = sub.add_parser("inspect")
    view.add_argument("run_id")
    view.add_argument("--show-content", action="store_true")
    view.add_argument("--history", action="store_true")
    sub.add_parser("diagrams")
    return p


def run_config(run_id):
    return {"configurable": {"thread_id": run_id}}


async def execute(args):
    root = Path(args.work_dir)
    root.mkdir(parents=True, exist_ok=True)
    if args.command == "diagrams":
        from apps.document_ingestion.workflows.document_ingestion.graph import (
            build_document_ingestion_graph,
        )
        from apps.retrieval.workflows.answer.graph import build_answer_graph

        for name, graph in [
            ("ingestion", build_document_ingestion_graph(object())),
            ("retrieval", build_answer_graph(service=object(), count_tokens=len)),
        ]:
            path = root / f"{name}.mmd"
            path.write_text(graph.get_graph().draw_mermaid(), encoding="utf-8")
            print(path)
        return 0
    factory = CheckpointerFactory(
        CheckpointSettings(backend="sqlite", sqlite_path=root / "checkpoints.sqlite")
    )
    async with factory.open() as saver:
        if args.command == "inspect":
            snapshot = await saver.aget_tuple(run_config(args.run_id))
            if snapshot is None:
                raise ValueError("Unknown run ID")
            values = snapshot.checkpoint.get("channel_values", {})
            if not args.local_access:
                raise ValueError(
                    "Inspect requires explicit --local-access to this local database"
                )
            output = {
                "run_id": args.run_id,
                "checkpoint_id": snapshot.checkpoint["id"],
                "metadata": snapshot.metadata,
                "state": values if args.show_content else state_summary(values),
            }
            if args.history:
                output["history"] = [
                    {"id": c.checkpoint["id"], "step": c.metadata.get("step")}
                    async for c in saver.alist(run_config(args.run_id))
                ]
            print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
            return 0
        args.allowed_root = args.allowed_root or [str(Path.cwd())]
        if args.factory:
            module, function = args.factory.split(":", 1)
            built = getattr(importlib.import_module(module), function)(args, saver)
            runtime, context = await built if inspect.isawaitable(built) else built
        else:
            from apps.pipelines.local import build_local_runtime

            runtime, context = build_local_runtime(args, saver)
        run_id = (
            args.run_id if args.command == "resume" else f"{args.workflow}-{uuid4()}"
        )
        graph = runtime.ingestion if args.workflow == "ingestion" else runtime.retrieval
        state = None
        if args.command == "ingest":
            path = args.file.resolve(strict=True)
            if not path.is_file() or not 0 < path.stat().st_size <= args.max_bytes:
                raise ValueError("Invalid input file size")
            source = SourceVersion(
                source=SourceRef(
                    source_id=args.source_id,
                    knowledge_space_id=args.space,
                    source_type="document",
                ),
                version=args.version,
            )
            document = DocumentInput(
                source=source, content=ContentRef(uri=path.as_uri())
            )
            mime = {
                ".md": "text/markdown",
                ".txt": "text/plain",
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }.get(path.suffix.lower())
            if mime is None:
                raise ValueError("Unsupported document extension")
            state = ingestion_state(
                document, filename=path.name, content_type=mime, profile=args.profile
            )
        elif args.command == "query":
            state = retrieval_state(
                SearchRequest(
                    query=args.question,
                    mode=args.mode,
                    top_k=args.top_k,
                    source_ids=args.source_id,
                ),
                generate=args.generate,
            )
        if args.workflow == "ingestion":
            if state is None:
                snapshot = await graph.aget_state(run_config(run_id))
                source = SourceVersion.model_validate(snapshot.values["source"])
            access = await runtime.authorization.authorize_action(
                context=context, source=source, action="ingest"
            )
            publish_access = await runtime.authorization.authorize_action(
                context=context, source=source, action="publish"
            )
            if access != publish_access:
                raise PermissionError("Ingest and publish metadata differ")
        else:
            access = context
        trace = PipelineTrace(
            root / "traces" / f"{run_id}.jsonl",
            run_id=run_id,
            workflow=args.workflow,
            echo=True,
        )
        print(f"run_id={run_id}", flush=True)
        result = await PipelineRunner().run(
            graph,
            state,
            options=GraphRunOptions(
                thread_id=run_id,
                context={"access": access},
                timeout_seconds=args.timeout,
                resume=args.command == "resume",
            ),
            trace=trace,
        )
        snapshot = await graph.aget_state(run_config(run_id))
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "next": list(snapshot.next),
                    "summary": state_summary(result),
                    "answer": result.get("answer"),
                    "evidence": result.get("evidence", []),
                    "trace": str(trace.path.with_suffix(".html")),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0


def main():
    args = parser().parse_args()
    try:
        return asyncio.run(execute(args))
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns a nonzero exit code
        if args.debug:
            import traceback

            traceback.print_exc()
        from apps.orchestration.errors import WorkflowFailed

        if isinstance(exc, WorkflowFailed):
            print(
                json.dumps(
                    {
                        "error_code": exc.error_code.value,
                        "step": exc.step,
                        "retryable": exc.retryable,
                    }
                )
            )
        else:
            print(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
