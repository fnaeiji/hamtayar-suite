"""One routing rule for all ingestion stages."""

from typing import Literal


def after_stage(state) -> Literal["next", "failure"]:
    return "failure" if state.get("status") == "failed" else "next"


after_load = after_parse = after_normalize = after_chunk = after_embed = after_index = (
    after_activate
) = after_stage
