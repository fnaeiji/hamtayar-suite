from packages.answering.service import validate_answer
from packages.contracts.answering import AnswerRequest
from packages.contracts.errors import ErrorCode

from apps.orchestration.errors import WorkflowFailed

from ._shared import results_from


def make_generate_answer_node(generator):
    async def generate_answer(state):
        if generator is None:
            raise WorkflowFailed(ErrorCode.PROVIDER_ERROR, step="generate_answer")
        evidence = results_from(state, "evidence")
        answer = validate_answer(
            await generator.generate(
                AnswerRequest(question=state["request"]["query"], evidence=evidence)
            ),
            evidence,
        )
        return {
            "answer": answer.model_dump(mode="json"),
            "status": "completed",
            "last_step": "generate_answer",
        }

    return generate_answer
