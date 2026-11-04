"""Checkpointer factories for LangGraph (MVP memory; optional persistent backend).

Checkpoint instances belong to the app Bootstrap lifespan, NOT to each request.
Never use the in-memory backend as durable production storage.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncContextManager, Literal


CheckpointProvider = Callable[[], AsyncContextManager[Any]]


@dataclass(frozen=True)
class CheckpointSettings:
    backend: Literal["memory", "sqlite", "custom"] = "memory"
    sqlite_path: Path | None = None

    def __post_init__(self) -> None:
        if self.backend == "sqlite" and self.sqlite_path is None:
            raise ValueError("sqlite_path is required for the sqlite checkpointer")
        if self.backend != "sqlite" and self.sqlite_path is not None:
            raise ValueError("sqlite_path is only valid for the sqlite checkpointer")


class CheckpointerFactory:
    """Choose a checkpoint backend, optionally supplied by another team.

    For a Postgres/Padeen-backed saver, inject an async context manager factory
    using backend='custom'. Do not place connection strings in code or logs.
    """

    def __init__(
        self,
        settings: CheckpointSettings | None = None,
        *,
        provider: CheckpointProvider | None = None,
    ) -> None:
        self.settings = settings if settings is not None else CheckpointSettings()
        self.provider = provider
        if self.settings.backend == "custom" and provider is None:
            raise ValueError("custom checkpointer requires an async context manager provider")
        if self.settings.backend != "custom" and provider is not None:
            raise ValueError("provider may only be used with backend='custom'")

    @asynccontextmanager
    async def open(self) -> AsyncIterator[Any]:
        """Keep this context open for as long as the compiled graphs use it."""
        if self.settings.backend == "memory":
            from langgraph.checkpoint.memory import InMemorySaver

            yield InMemorySaver()
        elif self.settings.backend == "sqlite":
            try:
                from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            except ImportError as exc:
                raise RuntimeError(
                    "SQLite checkpointing requires: uv add langgraph-checkpoint-sqlite"
                ) from exc
            assert self.settings.sqlite_path is not None
            # SQLite is local development only. The path must be trusted config.
            async with AsyncSqliteSaver.from_conn_string(str(self.settings.sqlite_path)) as saver:
                yield saver
        else:
            assert self.provider is not None
            async with self.provider() as saver:
                yield saver


def checkpoint_resource_factory(
    factory: CheckpointerFactory,
) -> Callable[[Any], AsyncContextManager[Any]]:
    """Adapter for BootstrapRegistry.resources['checkpointer']."""

    def resource(_settings: Any) -> AsyncContextManager[Any]:
        return factory.open()

    return resource
