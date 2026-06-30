# Quantum Building-Blocks API

Code generated in stage 4 can directly `import` and call the verified
functions below. Critical, error-prone quantum logic should reuse these
building blocks instead of being written from scratch.

## hamiltonians (`import hamiltonians`)

- `get_hamiltonian(molecule: str) -> SparsePauliOp`
  Returns the verified Hamiltonian operator (`qiskit.quantum_info.SparsePauliOp`)
  for the supported molecule. Molecule names are case-insensitive; unknown
  molecules raise `KeyError`.
- `supported_molecules() -> list[str]`
  Returns all supported molecule identifiers. Currently `["h2"]`.

## qaoa_blocks (`import qaoa_blocks`) — QAOA fast helpers (diagonal Ising)

**MANDATORY**: for diagonal cost Hamiltonians (`∑ c_i Z_i + ∑ J_ij Z_i Z_j`,
the standard form after converting QUBO to Ising) use this module. **Do not
use** `QAOAAnsatz(cost_operator=op) + Statevector(qc).expectation_value(op)`
— at N=12 a **single call takes 145 seconds** (qiskit internally goes through
scipy.sparse spsolve; 10 COBYLA iterations definitely exceeds the 150 s
sandbox timeout).

This module uses a hand-rolled cost layer (RZ + CNOT-RZ-CNOT) + mixer (RX) +
pure-numpy diagonal expectation value, taking **0.01 seconds** per call at
N=12 (15000x+ faster).

- `qubo_to_ising(Q) -> (h: ndarray, J: dict[(i,j) → float], const: float)`
  Convert an n×n QUBO matrix (min x^T Q x, x ∈ {0,1}^n) into an Ising
  H = ∑ h_i Z_i + ∑_{i<j} J_ij Z_i Z_j + const. `J` is a dict for space
  efficiency (only nonzero entries are stored).
- `qaoa_diag_circuit(n, diag_h, j_couplings, gamma, beta) -> QuantumCircuit`
  reps=1 QAOA circuit: Hadamard initialisation → cost layer → X mixer.
  `j_couplings` may be `None` (single-Z only).
- `expectation_diag_ising(state, n, diag_h, j_couplings) -> float`
  Computes `<state|H|state>` in pure numpy, O(2^N · N) complexity:
  N=12 = 0.008 s, N=14 = 0.04 s, N=16 = 0.2 s. **Completely bypasses qiskit
  `SparsePauliOp.to_matrix` / spsolve.**
- `decode_bitstring(state, n) -> str`
  Decode the optimal bitstring from `statevector.argmax`; bit `i` corresponds
  to qubit `i` (LSB-first, consistent with QUBO `x = [int(b) for b in bs]`).

Typical ~25-line usage (for cost = ∑ w_i x_i style QUBO):

```python
import numpy as np
from qiskit.quantum_info import Statevector
from scipy.optimize import minimize
import qaoa_blocks

# 1. Build the QUBO matrix (you write this yourself based on the spec)
Q = np.zeros((n, n))
for i, item in enumerate(block_items):
    Q[i, i] = float(item["cost"]) - lam * float(item["weight"])
# Off-diagonal / penalty terms come from cnf_blocks etc.

# 2. Convert to Ising
h, J, ising_const = qaoa_blocks.qubo_to_ising(Q)

# 3. QAOA cost function — use this module, not QAOAAnsatz
def cost(params):
    gamma, beta = params
    qc = qaoa_blocks.qaoa_diag_circuit(n, h, J, gamma, beta)
    sv = Statevector(qc)
    return qaoa_blocks.expectation_diag_ising(sv, n, h, J)

# 4. Optimise (maxiter=20 is enough; single cost evaluation is 0.01 s here,
#    total wall < 1 s)
x0 = np.array([0.1, 0.1])
res = minimize(cost, x0, method="COBYLA", options={"maxiter": 20})
best = res.x if res.x is not None else x0

# 5. Decode
sv = Statevector(qaoa_blocks.qaoa_diag_circuit(n, h, J, best[0], best[1]))
bitstring = qaoa_blocks.decode_bitstring(sv, n)
x = np.array([int(b) for b in bitstring], dtype=float)
value = float(x @ Q @ x)
```

When this module does not apply (use `QAOAAnsatz` instead): the cost contains
X / Y terms, or higher-order Pauli terms that are non-diagonal and not ZZ.
Partition-failure requests are almost always diagonal in form, and this
module covers them.

## cnf_blocks (`import cnf_blocks`) — CNF clauses → QUBO penalties

**Strongly recommended**: when the instance contains boolean constraint
clauses (typically of the form `{"id": 1, "constraint": "A1 or not C2"}`),
**use this module directly** rather than writing your own CNF parser plus
clause-to-quadratic-penalty expansion. Hand-written, this code is 200+ lines
with nested if/for indentation that easily breaks; in practice multiple
`codegen iterations exhausted` runs have failed exactly here.

- `parse_clause(clause: str) -> list[tuple[str, bool]]`
  Parses a single text clause (e.g. `"A1 or not C2"`) into
  `[(var, is_negated), ...]`. Supports `or` / `OR` / `|` connectives and
  `not` / `!` / `~` prefixes (case-insensitive). Empty / unparseable input
  raises `ValueError`.
- `parse_clauses(clauses: list[dict | str]) -> list[list[tuple[str, bool]]]`
  Batch parse. For dict form, takes the `["constraint"]` field; strings are
  passed straight to `parse_clause`.
- `clause_penalty_to_qubo(parsed_clauses, name_to_idx, n, penalty_weight=1.0) -> np.ndarray`
  Convert parsed clauses into an n×n upper-triangular QUBO penalty matrix.
  - `parsed_clauses`: output of `parse_clauses()`.
  - `name_to_idx`: `{variable_name: QUBO index 0..n-1}`. When partitioning,
    only pass the mapping for the current block.
  - `penalty_weight` λ: multiplier for the per-clause violation penalty.
  - Returns: `Q (n, n)`; `Q[i, i]` is linear, `Q[i, j]` (i<j) is quadratic,
    `Q[j, i] = 0` (upper-triangular).
  - Clauses that reference variables outside `name_to_idx` are skipped
    automatically (partition-friendly).
- `boolean_eval(bitstring, parsed_clauses, name_to_idx) -> (sat, vio)`
  After decoding the bitstring, count satisfied / violated clauses to feed
  back to verify diagnostics.

Typical ~15-line usage:

```python
import cnf_blocks
parsed = cnf_blocks.parse_clauses(instance["block_items"]["constraints"])
features = instance["block_items"]["features"]
name_to_idx = {f["name"]: i for i, f in enumerate(features)}
n = len(features)
costs = np.array([f["cost"] for f in features], dtype=float)
lam = 1.5 * float(costs.sum())
Q_pen = cnf_blocks.clause_penalty_to_qubo(parsed, name_to_idx, n,
                                            penalty_weight=lam)
Q = np.diag(costs) + Q_pen   # Total QUBO: cost + penalty
# Then move on to SKELETON step 2: build SparsePauliOp + QAOA from Q
```
