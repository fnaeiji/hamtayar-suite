import asyncio

from packages.answering.service import select_context
from packages.contracts.answering import AnswerResponse

from ._shared import dump, results_from


def make_build_context_node(*, count_tokens, max_tokens):
    async def build_context(state):
        evidence = await asyncio.to_thread(
            select_context,
            results_from(state),
            count_tokens=count_tokens,
            max_tokens=max_tokens,
        )
        answer = (
            None
            if evidence
            else AnswerResponse(answer="", status="no_evidence").model_dump(mode="json")
        )
        return {
            "evidence": dump(evidence),
            "answer": answer,
            "last_step": "build_context",
            "status": "running" if evidence and state.get("generate") else "completed",
        }

    return build_context
