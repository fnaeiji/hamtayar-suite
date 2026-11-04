
from pydantic import Field

from .common import ContractModel


class AccessMetadata(ContractModel):
    """Trusted access metadata attached to indexed content."""

    tenant_id: str = Field(min_length=1)
    acl_principals: list[str] = Field(min_length=1)


class TrustedAccessContext(ContractModel):
    """Identity and permissions supplied by a trusted system."""

    subject_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    principals: list[str] = Field(min_length=1)


class AccessScope(ContractModel):
    """Authorized scope used to restrict retrieval."""

    tenant_id: str = Field(min_length=1)
    principals: list[str] = Field(min_length=1)
    source_ids: list[str] | None = None
