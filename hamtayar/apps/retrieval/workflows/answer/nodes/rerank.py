from ._shared import dump, results_from


def make_rerank_node(reranker=None):
    async def rerank(state):
        before = results_from(state)
        if reranker is None:
            return {"last_step": "rerank", "reranked": False}
        after = list(
            await reranker.rerank(query=state["request"]["query"], results=before)
        )
        allowed = {r.evidence_id: r for r in before}
        if len({r.evidence_id for r in after}) != len(after) or any(
            allowed.get(r.evidence_id) != r for r in after
        ):
            raise ValueError("Reranker must only reorder or select retrieved evidence")
        return {"results": dump(after), "last_step": "rerank", "reranked": True}

    return rerank
