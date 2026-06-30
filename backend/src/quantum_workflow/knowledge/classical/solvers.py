"""Classical reference solvers.

A set of pure functions: take classical input, return a classical
reference solution. After the quantum code runs successfully, stage 5
calls the matching solver to compute a reference answer and cross-check
it against the quantum result.
"""
import itertools

import numpy as np
from qiskit.quantum_info import SparsePauliOp


def ground_state_energy(hamiltonian: SparsePauliOp) -> float:
    """Fully diagonalize the Hamiltonian and return the smallest eigenvalue (ground-state energy).

    Only applicable to small Hamiltonians whose dense matrix can be
    diagonalized directly with numpy.
    """
    eigvals = np.linalg.eigvalsh(hamiltonian.to_matrix())
    return float(eigvals.min())


def max_cut_value(n_nodes: int, edges: list[tuple[int, int]]) -> int:
    """Brute-force enumerate every 2-partition and return the max cut value.

    Only practical for small graphs whose node count makes 2^n
    enumeration acceptable.

    Args:
        n_nodes: Number of nodes in the graph.
        edges: Edge list, each entry (i, j); nodes are 0-indexed.
    """
    best = 0
    for assignment in itertools.product((0, 1), repeat=n_nodes):
        cut = sum(1 for (i, j) in edges if assignment[i] != assignment[j])
        best = max(best, cut)
    return best


def solve_instance(instance: dict) -> float:
    """Compute an exact classical solution for the problem instance returned by the quantum kernel, for stage-6 gate-B cross-check.

    Dispatched by instance["type"]:
      - "hamiltonian": instance["pauli_terms"] is [[pauli_str, coeff], ...].
        Build a SparsePauliOp, diagonalize exactly, and return the
        smallest eigenvalue.
      - "qubo": instance["matrix"] is an n x n symmetric QUBO matrix.
        Enumerate 2^n bitstrings and return the minimum value of
        x^T M x (requires n <= 20).

    Args:
        instance: Problem instance dict; must contain a "type" key.
    Raises:
        ValueError: Unknown instance type, or QUBO size beyond the enumeration limit.
    """
    kind = instance.get("type")
    if kind == "hamiltonian":
        try:
            terms = [(t[0], t[1]) for t in instance["pauli_terms"]]
        except KeyError as exc:
            raise ValueError(
                f"hamiltonian instance missing required field: {exc}") from exc
        return ground_state_energy(SparsePauliOp.from_list(terms))
    if kind == "qubo":
        try:
            matrix = np.array(instance["matrix"], dtype=float)
        except KeyError as exc:
            raise ValueError(
                f"qubo instance missing required field: {exc}") from exc
        n = matrix.shape[0]
        if n > 20:
            raise ValueError(f"QUBO size {n} exceeds brute-force enumeration limit of 20")
        best = float("inf")
        for bits in itertools.product((0, 1), repeat=n):
            x = np.array(bits, dtype=float)
            best = min(best, float(x @ matrix @ x))
        return best
    raise ValueError(f"unrecognized instance type: {kind!r}")
