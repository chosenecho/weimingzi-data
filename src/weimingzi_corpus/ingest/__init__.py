"""Local, deterministic incremental ingestion. No network or producer execution."""

from .errors import IngestError
from .manifest import verify_batch
from .planning import apply_batch, plan_batch, validate_repository

__all__ = [
    "IngestError",
    "verify_batch",
    "plan_batch",
    "apply_batch",
    "validate_repository",
]
