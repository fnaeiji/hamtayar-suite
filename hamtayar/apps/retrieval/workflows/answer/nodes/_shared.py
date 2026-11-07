from packages.contracts.access import TrustedAccessContext
from packages.contracts.errors import ErrorCode
from packages.contracts.retrieval import SearchResult

from apps.orchestration.errors import WorkflowFailed


def trusted_context(runtime):
    context = runtime.context or {}
    access = context.get("access")
    if not isinstance(access, TrustedAccessContext):
        raise WorkflowFailed(ErrorCode.ACCESS_DENIED, step="prefilter")
    return access


def results_from(state, field="results"):
    return [SearchResult.model_validate(item) for item in state.get(field, [])]


def dump(items):
    return [item.model_dump(mode="json") for item in items]
