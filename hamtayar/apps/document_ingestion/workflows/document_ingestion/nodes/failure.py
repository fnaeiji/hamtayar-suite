"""Surface an expected package failure with the shared error vocabulary."""

from packages.contracts.errors import ErrorCode

from apps.orchestration.errors import WorkflowFailed


def failed(state):
    raise WorkflowFailed(
        ErrorCode(state["error_code"]),
        step=state["error_step"],
        retryable=state.get("retryable", False),
    )
