"""SDK-neutral storage configuration for S-02."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Distance(str, Enum):
    """Project-owned distance vocabulary; mapped to the Qdrant SDK inside the adapter only."""

    COSINE = "Cosine"
    DOT = "Dot"
    EUCLID = "Euclid"
    MANHATTAN = "Manhattan"


@dataclass(frozen=True)
class StorageConfig:
    """Operational configuration and local-test defaults. Contains no SDK types."""

    url: str = "http://127.0.0.1:6333"
    collection_name: str = "hamtayar_test_chunks"
    vector_name: str = "dense"
    vector_size: int = 4
    distance: Distance = Distance.COSINE
    batch_size: int = 64
    timeout_seconds: float = 10.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("url must be non-empty")
        if not self.collection_name:
            raise ValueError("collection_name must be non-empty")
        if not self.vector_name:
            raise ValueError("vector_name must be non-empty")
        if self.vector_size <= 0:
            raise ValueError("vector_size must be greater than zero")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must not be negative")
