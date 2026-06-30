"""Data models and protocol for the asset repository.

Defines AssetMatch (a lookup result), Asset (a stored asset), and
AssetRepo (the Protocol interface). Every concrete repository
implementation must satisfy AssetRepo.
"""
from typing import Protocol

from pydantic import BaseModel, Field

from quantum_workflow.schemas.exec import ExecResult
from quantum_workflow.schemas.intent import ParsedIntent


class AssetMatch(BaseModel):
    """Asset-lookup result describing how closely a candidate matches the current intent.

    Fields:
        similarity: Similarity score against the query intent, range [0, 1].
        intent_overlap: List of intent tags overlapping with the query.
        adaptation_hints: List of LLM-suggested adaptation hints (default empty).
    """

    asset_id: str
    similarity: float = Field(..., ge=0.0, le=1.0)
    intent_overlap: list[str]
    asset_summary: str
    adaptation_hints: list[str] = Field(default_factory=list)


class Asset(BaseModel):
    """A fully stored asset, including code, intent, and execution result."""

    asset_id: str
    code: str
    intent: ParsedIntent
    exec_result: ExecResult


class AssetRepo(Protocol):
    """Structural-subtype protocol for an asset repository. Any class matching this protocol can serve as an implementation."""

    def lookup(self, intent: ParsedIntent, top_k: int = 5) -> list[AssetMatch]:
        """Return the top_k most similar asset candidates for an intent."""
        ...

    def save(
        self, request_id: str, code: str, intent: ParsedIntent, exec_result: ExecResult
    ) -> None:
        """Persist a newly generated code/exec_result pair as an asset."""
        ...

    def get(self, asset_id: str) -> Asset | None:
        """Load a single asset by id; return None when missing."""
        ...
