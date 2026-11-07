"""Shared in-process Document Ingestion execution for HTTP and CLI.

No queue, worker, Padeen client, fake production executor, or guessed graph state.
"""

import asyncio
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from apps.bootstrap import AppContainer, BootstrapRegistry
from apps.document_ingestion.api.schemas.jobs import (
    DocumentExecutionRequest,
    DocumentExecutionResult,
)
from apps.orchestration.graph_runtime import (
    GraphExecutionLayer,
    GraphRunOptions,
    document_thread_id,
)


class DocumentIngestionExecutor(Protocol):
    """Both HTTP and CLI invoke the same adapter contract."""

    async def execute(self, request: DocumentExecutionRequest) -> DocumentExecutionResult: ...


class AsyncCompiledGraph(Protocol):
    """Minimal LangGraph interface, independent of graph state implementation."""

    async def ainvoke(self, input: Mapping[str, Any]) -> Any: ...


class LangGraphDocumentExecutor:
    """Adapter for a compiled LangGraph with explicit state conversion.

    State shapes are deliberately injected: Graph state.py is owned by its
    implementation team and must not be guessed at the HTTP/CLI boundary.
    """

    def __init__(
        self,
        *,
        graph: AsyncCompiledGraph,
        to_state: Callable[[DocumentExecutionRequest], Mapping[str, Any]],
        from_state: Callable[[Any], DocumentExecutionResult],
        run_options_factory: Callable[[DocumentExecutionRequest], GraphRunOptions] | None = None,
        runner: GraphExecutionLayer | None = None,
    ) -> None:
        self._graph = graph
        self._to_state = to_state
        self._from_state = from_state
        self._run_options_factory = run_options_factory
        self._runner = runner if runner is not None else GraphExecutionLayer()

    async def execute(self, request: DocumentExecutionRequest) -> DocumentExecutionResult:
        state = self._to_state(request)
        if self._run_options_factory is None:
            # legacy adapter compatibility (including existing fakes).
            # For checkpointing, production MUST supply run_options_factory.
            graph_result = await self._graph.ainvoke(state)
        else:
            options = self._run_options_factory(request)
            graph_result = await self._runner.execute(
                self._graph, None if options.resume else state, options=options,
            )
        return self._from_state(graph_result)


def document_run_options(
    request: DocumentExecutionRequest,
    *,
    timeout_seconds: float,
    context: Mapping[str, Any] | None = None,
    resume: bool = False,
) -> GraphRunOptions:
    """Stable thread identity for same source across HTTP and CLI."""
    source = request.document.source
    return GraphRunOptions(
        thread_id=document_thread_id(
            knowledge_space_id=source.source.knowledge_space_id,
            source_id=source.source.source_id,
            version=source.version,
            processing_profile=request.processing_profile,
        ),
        timeout_seconds=timeout_seconds,
        context=context if context is not None else {},
        resume=resume,
    )


class ExecutorUnavailable(RuntimeError):
    """No registered Document Ingestion executor (no silent fake fallback)."""


class DocumentExecutionTimedOut(RuntimeError):
    """Direct execution exceeded its configured deadline."""


class DocumentExecutionFailed(RuntimeError):
    """Executor raised or returned an invalid result (internal details hidden)."""


def get_runtime_registry() -> BootstrapRegistry:
    """Single default registry factory for HTTP and CLI.

    Intentionally empty until a real Document Ingestion Graph is registered.
    Future wiring belongs HERE, not in CLI/HTTP-specific code. Do not insert
    fake services as a production default.
    """
    return BootstrapRegistry()


def resolve_document_ingestion_executor(container: AppContainer) -> DocumentIngestionExecutor:
    """Read an already-initialized executor, never create a client per call."""
    executor = container.services.get("document_ingestion_executor")
    if executor is None or not callable(getattr(executor, "execute", None)):
        raise ExecutorUnavailable("Document ingestion executor is not configured")
    return executor


async def run_document_ingestion(
    executor: DocumentIngestionExecutor,
    request: DocumentExecutionRequest,
    *,
    timeout_seconds: float,
) -> DocumentExecutionResult:
    """Await a complete result, with consistent validation and timeout semantics.

    Executor implementations must cooperate with cancellation. This function
    does not spawn background tasks, queues, or detached threads.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    try:
        result = await asyncio.wait_for(executor.execute(request), timeout_seconds)
    except TimeoutError as exc:
        raise DocumentExecutionTimedOut("Document processing timed out") from exc
    except Exception as exc:
        raise DocumentExecutionFailed("Document processing failed") from exc

    if not isinstance(result, DocumentExecutionResult) or (
        result.chunks_indexed is not None
        and (isinstance(result.chunks_indexed, bool) or result.chunks_indexed < 0)
    ):
        raise DocumentExecutionFailed("Document processing returned an invalid result")
    return result


class PipelineRunner:
    """Shared streaming invocation for local tracing, breakpoints and resume."""

    async def run(self, graph, initial_state, *, options, trace):
        import hashlib
        import json
        from time import perf_counter

        from packages.contracts.errors import ErrorCode

        from apps.core.observability import state_summary
        from apps.orchestration.checkpointer import record_pipeline_checkpoint
        from apps.orchestration.errors import WorkflowFailed

        config = options.runnable_config()
        config['run_name'] = trace.workflow
        access = options.context.get('access')
        if access is None:
            raise WorkflowFailed(ErrorCode.ACCESS_DENIED, step='start')
        fingerprint = hashlib.sha256(json.dumps(access.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
        if options.resume:
            if initial_state is not None:
                raise ValueError('Resume cannot accept new input')
            snapshot = await graph.aget_state(config)
            if not snapshot.values or snapshot.values.get('_context_fingerprint') != fingerprint:
                raise WorkflowFailed(ErrorCode.ACCESS_DENIED, step='resume')
            if not snapshot.next:
                raise ValueError('This run has already finished')
        else:
            if initial_state is None:
                raise ValueError('New runs require input')
            snapshot = await graph.aget_state(config)
            if snapshot.values:
                raise ValueError('Run ID already exists; resume it or use a new ID')
            initial_state = {**initial_state, '_context_fingerprint': fingerprint}
        started, node, tasks = perf_counter(), 'start', {}
        values = initial_state or {}
        trace.record('resumed' if options.resume else 'started', status='running')
        try:
            async with asyncio.timeout(options.timeout_seconds):
                async for mode, payload in graph.astream(initial_state, config=config,
                    context=dict(options.context), stream_mode=['tasks', 'updates', 'checkpoints', 'values'], durability='sync'):
                    if mode == 'tasks':
                        node = payload.get('name', node)
                        task_id = payload.get('id', node)
                        if 'input' in payload:
                            tasks[task_id] = perf_counter()
                            trace.record('node_started', node=node, task_id=task_id)
                        else:
                            trace.record('node_failed' if payload.get('error') else 'node_finished',
                                node=node, task_id=task_id, duration_ms=round((perf_counter()-tasks.pop(task_id, perf_counter()))*1000, 3))
                    elif mode == 'checkpoints':
                        record_pipeline_checkpoint(trace, payload)
                    elif mode == 'values':
                        values = payload
                    elif mode == 'updates':
                        for name, update in payload.items():
                            if isinstance(update, dict):
                                trace.record('state_update', node=name, **state_summary(update))
            snapshot = await graph.aget_state(config)
            values = dict(snapshot.values)
            trace.record('paused' if snapshot.next else 'completed', next=list(snapshot.next),
                         duration_ms=round((perf_counter()-started)*1000, 3), **state_summary(values))
            return values
        except Exception as exc:
            code = getattr(exc, 'error_code', None)
            if not isinstance(code, ErrorCode):
                code = ErrorCode.ACCESS_DENIED if isinstance(exc, PermissionError) else (
                    ErrorCode.VALIDATION_ERROR if isinstance(exc, ValueError) else ErrorCode.PROCESSING_FAILED)
            trace.record('failed', node=node, error_code=code.value,
                         retryable=getattr(exc, 'retryable', isinstance(exc, (TimeoutError, ConnectionError))))
            if isinstance(exc, WorkflowFailed):
                raise
            raise WorkflowFailed(code, step=node, retryable=getattr(exc, 'retryable', isinstance(exc, (TimeoutError, ConnectionError)))) from exc
        finally:
            trace.render()
