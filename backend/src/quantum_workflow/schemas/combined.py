# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Combine-stage data models: aggregate N sub-results into a complete solution to the original problem."""

from pydantic import BaseModel, Field


class CombinedResult(BaseModel):
    """Output of stage 7 (combine): full solution to the original problem + sub-result summaries + combine log.

    The verify stage cross-checks against this, not against any
    individual decomposed sub-problem.
    """

    value: float | dict                          # full-problem solution value
    instance: dict                               # full-problem instance (input to verify gate B)
    subresults_summary: list[dict] = Field(default_factory=list)
                                                 # per-sub-result summary (value + sub_id)
    combine_log: str = ""                        # brief log of the combine process
