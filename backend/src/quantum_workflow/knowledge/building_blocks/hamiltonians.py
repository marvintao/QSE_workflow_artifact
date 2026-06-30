"""Quantum building block: verified molecular Hamiltonians.

Each entry is a qiskit SparsePauliOp built from published coefficients.
These are validated "blocks": stage-4 generated code can import them
directly, and stage-5 classical cross-checks can reuse them as well.
The LLM never produces these numerical values.
"""
from qiskit.quantum_info import SparsePauliOp

# H2 Hamiltonian at 0.74 angstroms in the STO-3G basis under parity
# mapping with 2-qubit reduction. Coefficients are in Hartree (the II
# term includes the nuclear-repulsion energy; the ground-state
# eigenvalue is approximately -1.137 Ha). Values taken from Kandala
# et al. 2017 / standard VQE references.
_H2 = SparsePauliOp.from_list([
    ("II", -0.33726885524029415),
    ("IZ", 0.39793742484318045),
    ("ZI", -0.39793742484318045),
    ("ZZ", -0.01128010425623538),
    ("XX", 0.18093119978423156),
])

_HAMILTONIANS = {
    "h2": _H2,
}


def get_hamiltonian(molecule: str) -> SparsePauliOp:
    """Return the validated Hamiltonian operator for a supported molecule.

    Args:
        molecule: Molecule identifier; case-insensitive.
    Returns:
        The corresponding SparsePauliOp. Raises KeyError for an unknown molecule.
    """
    key = molecule.strip().lower()
    if key not in _HAMILTONIANS:
        raise KeyError(f"no curated Hamiltonian for molecule {molecule!r}")
    return _HAMILTONIANS[key]


def supported_molecules() -> list[str]:
    """Return all supported molecule identifiers (sorted)."""
    return sorted(_HAMILTONIANS)
