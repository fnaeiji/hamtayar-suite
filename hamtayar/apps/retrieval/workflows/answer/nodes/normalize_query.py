import asyncio


def make_normalize_query_node(service):
    async def normalize_query(state):
        request = dict(state["request"])
        request["query"] = await asyncio.to_thread(service.normalize, request["query"])
        return {"request": request, "last_step": "normalize_query"}

    return normalize_query
