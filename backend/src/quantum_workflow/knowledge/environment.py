# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Execution-environment facts: algorithm-agnostic notes about the target environment and its API, injected into stage 4."""
from pathlib import Path

_DOC = Path(__file__).resolve().parent / "environment.md"


def environment_facts() -> str:
    """Return the execution-environment facts document (Qiskit 2.x API ground truth) for injection into codegen prompts."""
    return _DOC.read_text(encoding="utf-8")
