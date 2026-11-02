# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Intent-parsing stage data models: structured intent extracted by the LLM from a raw user requirement."""

from pydantic import BaseModel, Field


class ParsedIntent(BaseModel):
    """Structured intent object produced by the LLM from a raw user requirement."""

    domain: str = Field(..., description="Problem domain, e.g. chemistry")  # problem domain, e.g. chemistry
    problem_statement: str                                                    # normalized problem statement
    constraints: dict[str, str] = Field(default_factory=dict)               # explicit user constraints; keys and values are strings
    data_scale_hints: dict[str, int] = Field(default_factory=dict)          # data-scale hints, e.g. qubit count, molecule size
    ambiguities: list[str] = Field(default_factory=list)                    # ambiguities or clarifications detected by the LLM
    # Concrete instance data extracted from raw_text (typical: test-case
    # JSON list or QUBO matrix). After encoding has produced blocks, the
    # orchestrator slices this per variable_start/end and injects the
    # slice into each block's SubProblem.instance.block_items so that
    # codegen can access the real data for that block.
    instance_data: list | dict | None = None
