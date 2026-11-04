"""Composition root: create shared resources, services and compiled graphs once."""

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import AsyncContextManager

from fastapi import Request

from apps.core.config import Settings

# Keep this layer independent of other teams' unfinished contract modules.
ResourceFactory = Callable[[Settings], AsyncContextManager[object]]
ServiceFactory = Callable[[Settings, Mapping[str, object]], object]
GraphFactory = Callable[[Settings, Mapping[str, object], Mapping[str, object]], object]


@dataclass(frozen=True)
class BootstrapRegistry:
    """Factories are explicitly registered by the application's entry point."""

    resources: Mapping[str, ResourceFactory] = field(default_factory=dict)
    services: Mapping[str, ServiceFactory] = field(default_factory=dict)
    graphs: Mapping[str, GraphFactory] = field(default_factory=dict)


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    resources: Mapping[str, object]
    services: Mapping[str, object]
    graphs: Mapping[str, object]


@asynccontextmanager
async def bootstrap(
    settings: Settings,
    registry: BootstrapRegistry | None = None,
) -> AsyncIterator[AppContainer]:
    """Open resources once per application lifespan, then close in reverse order.

    Factories should return already-constructed services/graphs using resources
    supplied here; they must not create unmanaged clients per request.
    """
    registered = registry if registry is not None else BootstrapRegistry()

    async with AsyncExitStack() as stack:
        resources: dict[str, object] = {}
        for name, factory in registered.resources.items():
            resources[name] = await stack.enter_async_context(factory(settings))

        shared_resources = MappingProxyType(resources)
        services = {
            name: factory(settings, shared_resources)
            for name, factory in registered.services.items()
        }
        shared_services = MappingProxyType(services)
        graphs = {
            name: factory(settings, shared_resources, shared_services)
            for name, factory in registered.graphs.items()
        }

        yield AppContainer(
            settings=settings,
            resources=shared_resources,
            services=shared_services,
            graphs=MappingProxyType(graphs),
        )


def get_container(request: Request) -> AppContainer:
    """FastAPI dependency; never creates new clients or graphs."""
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, AppContainer):
        raise RuntimeError("Application dependencies are not initialized")
    return container
