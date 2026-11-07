"""Bound evidence and validate generated citations independently of any LLM SDK."""

from packages.contracts.answering import AnswerResponse


def select_context(results, *, count_tokens, max_tokens: int):
    selected, used = [], 0
    for result in results:
        if not result.text or not result.text.strip():
            continue
        cost = count_tokens(result.text + "\n" + result.evidence_id)
        if cost < 1:
            raise ValueError("Invalid context token count")
        if used + cost <= max_tokens:
            selected.append(result)
            used += cost
    return selected


def validate_answer(answer: AnswerResponse, evidence):
    if not isinstance(answer, AnswerResponse) or answer.status != "completed":
        raise ValueError("Invalid generated answer")
    allowed = {item.evidence_id: item for item in evidence}
    if not answer.answer.strip() or not answer.citations:
        raise ValueError("A grounded answer requires text and citations")
    for citation in answer.citations:
        item = allowed.get(citation.evidence_id)
        if (
            item is None
            or citation.source != item.source
            or citation.location != item.location
        ):
            raise ValueError("Citation does not match authorized evidence")
    return answer
