"""Quantum-opportunity analysis stage data models.

Output of stage 2: the problem decomposition plus the identified quantum
kernel. The algorithm is chosen by the LLM; the system does not maintain
a preset algorithm catalog.
"""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SubTask(BaseModel):
    """A decomposed sub-task together with its classical/quantum classification."""

    name: str
    description: str
    disposition: Literal["classical", "quantum"]


class QuantumKernel(BaseModel):
    """Identified quantum kernel: the algorithm chosen by the LLM along with its spec.

    `algorithm` is free-form text and is not validated against any
    catalog — algorithm choice is fully delegated to the LLM.
    """

    algorithm: str                # algorithm name chosen by the LLM, e.g. "VQE" / "QAOA"
    algorithm_rationale: str      # rationale for choosing this algorithm
    subproblem: str               # description of the sub-problem this kernel solves exactly
    io_interface: str             # how the classical part supplies inputs and consumes outputs
    full_scale_qubits: int        # qubits required by the full-scale requirement
    feasible_qubits: int          # feasible budget of the system (echoed back for traceability)
    # Whether reduction is needed is derived from
    # `reduced_qubits < full_scale_qubits` (see the needs_reduction
    # property); it is not stored separately — the encode stage is where
    # the actual decomposition is decided.
    reduced_qubits: int           # actual run-scale; equals full_scale_qubits when no reduction is needed
    reduction_note: str = ""      # what was reduced / what full scale would require; empty when no reduction


    @property
    def needs_reduction(self) -> bool:
        """Derived: True iff the run-scale is strictly smaller than the full scale."""
        return self.reduced_qubits < self.full_scale_qubits


class QuantumOpportunity(BaseModel):
    """Output of stage 2 (quantum opportunity analysis)."""

    decomposition: list[SubTask]
    # quantum_kernel is None when the requirement has no quantum-amenable part.
    quantum_kernel: QuantumKernel | None = None
    # When quantum_kernel is None, this records why there is no quantum advantage.
    no_quantum_reason: str | None = None

    @model_validator(mode="after")
    def _check_kernel_reason_coherence(self) -> "QuantumOpportunity":
        """Exactly one of quantum_kernel / no_quantum_reason must be None."""
        has_kernel = self.quantum_kernel is not None
        has_reason = self.no_quantum_reason is not None
        if has_kernel == has_reason:  # both set or both unset -- semantic contradiction
            raise ValueError(
                "Exactly one of quantum_kernel / no_quantum_reason must be None")
        return self
