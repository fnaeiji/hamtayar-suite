
from typing import Literal

from pydantic import Field

from .common import (
    ContractModel,
    ContentRef,
    SourceLocation,
    SourceVersion,
)


class CodeAnalysisRequest(ContractModel):
    """Input contract for repository analysis."""

    source: SourceVersion
    content: ContentRef
    provider_id: str = "internal"


class CodeSymbol(ContractModel):
    """A structural entity extracted from source code."""

    symbol_id: str
    name: str
    kind: str
    location: SourceLocation
    signature: str | None = None
    content: str | None = None


class CodeRelationship(ContractModel):
    """A relationship between code entities."""

    source_symbol_id: str
    target_symbol_id: str
    kind: Literal["CONTAINS", "IMPORTS", "DEFINES", "EXTENDS"]


class CodeAnalysisResult(ContractModel):
    """Standard result of code analysis."""

    source: SourceVersion
    provider_id: str
    symbols: list[CodeSymbol] = Field(default_factory=list)
    relationships: list[CodeRelationship] = Field(default_factory=list)
    index_handle: str | None = None
    index_generation: str | None = None
    warnings: list[str] = Field(default_factory=list)
