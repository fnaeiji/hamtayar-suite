"""Checkpoint-friendly retrieval state; credentials remain in runtime context."""

from typing import TypedDict

from packages.contracts.access import TrustedAccessContext

STAGES = (
    "prefilter",
    "normalize_query",
    "retrieve",
    "rerank",
    "reauthorize",
    "build_context",
    "generate_answer",
)


class RetrievalRuntimeContext(TypedDict):
    access: TrustedAccessContext


class AnswerState(TypedDict, total=False):
    _context_fingerprint: str
    request: dict
    generate: bool
    scope: dict
    active: list[dict]
    results: list[dict]
    evidence: list[dict]
    answer: dict | None
    partial: bool
    warnings: list[str]
    status: str
    last_step: str
    error_code: str
    reranked: bool


def initial_state(request, *, generate=False) -> AnswerState:
    return {
        "request": request.model_dump(mode="json"),
        "generate": generate,
        "results": [],
        "evidence": [],
        "answer": None,
        "status": "pending",
    }
