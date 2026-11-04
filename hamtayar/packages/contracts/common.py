from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    """Base model for all shared contracts."""

    model_config = ConfigDict(extra="forbid")


class SourceRef(ContractModel):
    source_id: str = Field(min_length=1)
    knowledge_space_id: str = Field(min_length=1)
    source_type: Literal["document", "repository"]


class SourceVersion(ContractModel):
    source: SourceRef
    version: str = Field(min_length=1)


class ContentRef(ContractModel):
    """Reference to content stored outside the contract layer."""

    uri: str = Field(min_length=1)


class SourceLocation(ContractModel):
    """Location of evidence in the original decoded source.

    Line numbers are one-based and ``end_line`` is inclusive. They are not
    offsets into cleaned or normalized text. A code block's range may include
    Markdown fences although its extracted text contains only the code payload.
    Parsers exclude blank separator lines from block ranges consistently. Page,
    sheet, and cell fields remain optional for formats that provide them.
    """

    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    sheet: str | None = None
    cell_range: str | None = None
    file_path: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_line_range(self):
        if self.end_line is not None and (
            self.start_line is None or self.end_line < self.start_line
        ):
            raise ValueError("Invalid source line range")
        return self
