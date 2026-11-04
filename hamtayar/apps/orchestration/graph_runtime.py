"""Shared LangGraph invocation, checkpoint state inspection and retry policies.

This layer handles how a compiled graph runs, not domain-specific Graph state.
The same runner can serve document ingestion and answer generation.
"""

import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


class GraphExecutionTimedOut(TimeoutError):
    """Graph did not finish before the configured deadline."""


class GraphExecutionFailed(RuntimeError):
    """Graph failed; internal exception remains available as __cause__."""


class GraphStateUnavailable(RuntimeError):
    """Compiled graph does not provide the async checkpoint inspection API."""


class CompiledGraph(Protocol):
    """The portion of CompiledStateGraph used by the shared runner."""

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class GraphRunOptions:
    """Run-specific settings. Reusing thread_id addresses the *same* history.

    Passing resume=True invokes with input=None, resuming the existing
    checkpoint. A fresh input with a repeated ID is a *new* invocation, not a
    resume. Do not combine resume=True with new input data.
    """

    thread_id: str
    timeout_seconds: float = 30.0
    context: Mapping[str, Any] = field(default_factory=dict)
    recursion_limit: int = 50
    durability: Literal["sync", "async", "exit"] = "sync"
    resume: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.thread_id, str) or not self.thread_id.strip() or len(self.thread_id) > 255:
            raise ValueError("thread_id must be a nonempty string of at most 255 characters")
        if self.thread_id != self.thread_id.strip():
            raise ValueError("thread_id must not have surrounding whitespace")
        if not isinstance(self.timeout_seconds, (float, int)) or not 0 < self.timeout_seconds <= 3600:
            raise ValueError("timeout_seconds must be between 0 and 3600")
        if not isinstance(self.recursion_limit, int) or self.recursion_limit < 2:
            raise ValueError("recursion_limit must be at least 2")
        if self.durability not in ("sync", "async", "exit"):
            raise ValueError("Unsupported durability mode")
        if not isinstance(self.context, Mapping):
            raise ValueError("context must be a mapping")

    def runnable_config(self) -> dict[str, Any]:
        return {
            "configurable": {"thread_id": self.thread_id},
            "recursion_limit": self.recursion_limit,
        }


class GraphExecutionLayer:
    """One invocation interface for all compiled LangGraph workflows.

    No automatic whole-graph retry: use node RetryPolicy only on safe steps.
    Cancellation is cooperative; blocking I/O in nodes is not interrupted.
    """

    async def execute(
        self,
        graph: CompiledGraph,
        initial_state: Any,
        *,
        options: GraphRunOptions,
    ) -> Any:
        if options.resume and initial_state is not None:
            raise ValueError("Resume requires initial_state=None")
        if not options.resume and initial_state is None:
            raise ValueError("A new execution requires an initial_state")

        try:
            return await asyncio.wait_for(
                graph.ainvoke(
                    None if options.resume else initial_state,
                    config=options.runnable_config(),
                    context=dict(options.context) if options.context else None,
                    durability=options.durability,
                ),
                timeout=options.timeout_seconds,
            )
        except TimeoutError as exc:
            raise GraphExecutionTimedOut("Graph execution timed out") from exc
        except Exception as exc:
            raise GraphExecutionFailed("Graph execution failed") from exc

    async def get_state(self, graph: Any, *, thread_id: str) -> Any:
        """Read the latest checkpoint state using exactly the same thread ID."""
        options = GraphRunOptions(thread_id=thread_id)
        method = getattr(graph, "aget_state", None)
        if not callable(method):
            raise GraphStateUnavailable("Graph does not expose aget_state")
        return await method(options.runnable_config())


class IdempotentSideEffect(Protocol):
    """Required port for external writes (e.g. vector indexing, publication).

    Implementations must persistently deduplicate by idempotency_key. Merely
    generating a stable key is NOT enough to make side effects idempotent.
    """

    async def apply(
        self, *, idempotency_key: str, payload: Mapping[str, Any]
    ) -> Any: ...


def make_node_retry_policy(
    *,
    retry_on: Sequence[type[Exception]],
    max_attempts: int = 2,
    initial_interval: float = 0.1,
) -> Any:
    """Explicit per-node retry, restricted to transient exception classes.

    Use: builder.add_node('fetch', fetch, retry_policy=make_node_retry_policy(
        retry_on=(TemporaryProviderError,), max_attempts=2))
    """
    if not retry_on or any(not isinstance(exc, type) or not issubclass(exc, Exception) for exc in retry_on):
        raise ValueError("retry_on must contain explicit Exception subclasses")
    if not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if initial_interval < 0:
        raise ValueError("initial_interval cannot be negative")

    from langgraph.types import RetryPolicy

    return RetryPolicy(
        max_attempts=max_attempts,
        initial_interval=initial_interval,
        jitter=False,
        retry_on=tuple(retry_on),
    )


def stable_idempotency_key(*, workflow: str, source_id: str, version: str, step: str, namespace: str) -> str:
    """Deterministic operation ID; external adapter must enforce deduplication.

    `namespace` must include tenant/knowledge-space identity to prevent
    collisions across tenants. Never use this function alone as an ACL check.
    """
    if not all(isinstance(v, str) and v for v in (workflow, source_id, version, step, namespace)):
        raise ValueError("Idempotency key components must be nonempty strings")
    payload = json.dumps([namespace, workflow, source_id, version, step], separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def document_thread_id(*, knowledge_space_id: str, source_id: str, version: str, processing_profile: str) -> str:
    """Stable ID for the same document/version/profile across HTTP and CLI."""
    key = stable_idempotency_key(
        namespace=knowledge_space_id,
        workflow="document_ingestion",
        source_id=source_id,
        version=version,
        step=processing_profile,
    )
    return f"document-{key}"
