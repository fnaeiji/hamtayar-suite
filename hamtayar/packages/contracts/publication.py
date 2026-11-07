"""Persistence contract for validated index generations and atomic promotion."""

from typing import Protocol

from packages.contracts.access import AccessMetadata
from packages.contracts.common import SourceVersion


class GenerationCatalog(Protocol):
    async def mark_validated(
        self,
        *,
        source: SourceVersion,
        access: AccessMetadata,
        generation_id: str,
        indexed_count: int,
    ) -> None: ...

    async def publish(
        self,
        *,
        source: SourceVersion,
        access: AccessMetadata,
        generation_id: str,
    ) -> bool: ...

    async def active_generations(
        self, *, scope: "AccessScope"
    ) -> list["ActiveGeneration"]: ...

    async def active_generation(
        self,
        *,
        source: SourceVersion,
        access: AccessMetadata,
    ) -> str | None: ...


from dataclasses import dataclass

from packages.contracts.access import AccessScope


@dataclass(frozen=True)
class ActiveGeneration:
    source: SourceVersion
    generation_id: str
