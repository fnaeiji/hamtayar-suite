"""Stop before model generation when no authorized context remains."""

from typing import Literal


def after_context(state) -> Literal["generate", "done"]:
    return "generate" if state.get("evidence") and state.get("generate") else "done"
