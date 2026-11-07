"""Errors shared by graph runners, without HTTP or provider-specific details."""

from packages.contracts.errors import ErrorCode


class WorkflowFailed(RuntimeError):
    def __init__(self, code: ErrorCode, *, step: str, retryable: bool = False):
        self.error_code, self.step, self.retryable = code, step, retryable
        super().__init__(f"{step}: {code.value}")
