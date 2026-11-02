# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Code-generation stage data models: the LLM-produced quantum-workflow code and its coverage report."""

from pydantic import BaseModel


class CoverageReport(BaseModel):
    """Records how completely the generated code covers the planned workflow nodes."""

    planned_nodes: list[str]  # all node IDs in the workflow plan
    covered_nodes: list[str]  # node IDs actually covered by the generated code

    @property
    def ratio(self) -> float:
        """Coverage ratio (0.0-1.0); empty planned_nodes is treated as full coverage."""
        if not self.planned_nodes:
            return 1.0
        raw = len(self.covered_nodes) / len(self.planned_nodes)
        return min(raw, 1.0)  # guard against malformed data pushing the ratio above 1.0


class GeneratedCode(BaseModel):
    """Complete code artifact produced by the LLM for the quantum workflow."""

    code: str                          # generated Python source as a string
    entry_point: str = "main"          # entry-point function name; defaults to "main"
    requirements: list[str]            # required Python packages
    coverage: CoverageReport           # node-coverage report
    fill_diff: str = ""                # description of parameter-fill changes relative to the template skeleton
    aux_files: dict[str, str] = {}     # auxiliary file map: filename -> contents
