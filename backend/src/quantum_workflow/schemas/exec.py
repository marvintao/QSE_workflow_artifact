# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Code-execution stage data models: execution status, result, and verification state for quantum-circuit runs."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExecStatus(str, Enum):
    """Terminal status of a code-execution attempt."""

    SUCCESS = "success"              # executed successfully
    RUNTIME_ERROR = "runtime_error"  # raised a runtime exception
    RESOURCE_LIMIT = "resource_limit"  # exceeded a resource limit (time or memory)


class VerificationStatus(str, Enum):
    """Verification status after execution and the dual-gate check."""

    CROSS_CHECKED = "cross_checked"  # gates A and B both pass
    UNVERIFIED = "unverified"        # ran successfully but no numerical cross-check available
    MISMATCH = "mismatch"            # gate A passes, gate B fails: result disagrees with classical reference
    OFF_SPEC = "off_spec"            # gate A fails: the code is solving the wrong problem
    FAILED = "failed"                # still unable to run after N repair rounds


class RepairAttempt(BaseModel):
    """A single round in the self-repair loop."""

    attempt: int   # repair round number (1-indexed)
    error: str     # summary of the error that triggered this round


class ExecResult(BaseModel):
    """Result envelope returned after code execution (including the repair loop and classical cross-check)."""

    status: ExecStatus                              # status of the final execution
    result: dict[str, Any] | None = None           # numerical result on success; None on failure
    metrics: dict[str, Any] = Field(default_factory=dict)  # performance metrics, e.g. duration
    stderr_excerpt: str | None = None              # excerpt of stderr when execution fails
    # -- Fields added by the generative pipeline; defaults preserve backward compatibility for older callers --
    verification_status: VerificationStatus | None = None  # verification status
    repair_history: list[RepairAttempt] = Field(default_factory=list)  # repair history
