"""Workflow-planning stage data models: the quantum-workflow DAG produced by the LLM and its feasibility assessment."""

from typing import Literal

from pydantic import BaseModel, Field


class Feasibility(BaseModel):
    """Feasibility assessment of the workflow on the target hardware."""

    qubit_count: int       # qubits required by the workflow
    estimated_depth: int   # estimated circuit depth
    passes_limits: bool    # whether the workflow fits the hardware budget (qubit count and depth both within limits)


class BlueprintNode(BaseModel):
    """A node in the hybrid workflow blueprint, marked classical or quantum."""

    id: str
    name: str
    kind: Literal["classical", "quantum"]  # node kind
    description: str
    inputs: list[str] = Field(default_factory=list)   # input data names
    outputs: list[str] = Field(default_factory=list)  # output data names


class BlueprintEdge(BaseModel):
    """A directed dataflow edge in the blueprint."""

    from_id: str
    to_id: str


class WorkflowBlueprint(BaseModel):
    """Output of stage 3 (hybrid blueprint): an end-to-end DAG of classical and quantum nodes."""

    nodes: list[BlueprintNode]
    edges: list[BlueprintEdge] = Field(default_factory=list)
    feasibility: Feasibility

    @property
    def quantum_nodes(self) -> list[BlueprintNode]:
        """Return every quantum node — only these feed into stage 4 code generation."""
        return [n for n in self.nodes if n.kind == "quantum"]
