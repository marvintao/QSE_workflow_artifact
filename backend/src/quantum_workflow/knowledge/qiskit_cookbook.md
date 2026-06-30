# Qiskit 2.x API Usage Snippets

The correct way to call specific APIs. These are **library API documentation
snippets**, not algorithm implementations — the overall structure of a quantum
algorithm is yours to design. Each snippet stands alone and can be composed
as needed; do not copy them verbatim as the structure of your program.

## Simulator backend `AerSimulator`

```python
from qiskit_aer import AerSimulator   # Note: imported from qiskit_aer, not qiskit
sim = AerSimulator()
```

## Parameterised ansatz `efficient_su2` (VQE-style, do not use for a QAOA kernel)

```python
from qiskit.circuit.library import efficient_su2
ansatz = efficient_su2(num_qubits=4, reps=2, entanglement="linear")
# The ansatz is a QuantumCircuit; the number of parameters is ansatz.num_parameters
```

`efficient_su2` is a hardware-efficient / VQE-style ansatz and **does not have
the alternating cost-Hamiltonian structure**. Use it only when
`kernel.algorithm == "VQE"` (molecular Hamiltonian ground state, fixed
operator-type problems).

**If `kernel.algorithm == "QAOA"`, you must use `QAOAAnsatz` (next section)
rather than `efficient_su2`** — the verify agent runs a gate-A check against
the algorithm declared by the kernel, and a silent swap to `efficient_su2`
will be flagged `off_spec: algorithm mismatch`. Typical reason quote:
"kernel declares QAOA, but the code uses an `efficient_su2` variational
circuit in place of a QAOA circuit (QAOA requires the alternating
cost-Hamiltonian + mixer-Hamiltonian structure)".

## QAOA ansatz `QAOAAnsatz`

```python
from qiskit.circuit.library import QAOAAnsatz
# Qiskit 2.x: the parameter name is `cost_operator=` (keyword), not `operator=`.
# QAOAAnsatz(operator=op, reps=p) from qiskit 1.x training memory will raise
#   TypeError: QAOAAnsatz.__init__() got an unexpected keyword argument 'operator'
# Repeatedly rewriting with operator= is a classic trap from LLM training data
# stuck on 1.x — use cost_operator= and the issue disappears immediately.
ansatz = QAOAAnsatz(cost_operator=op, reps=1)
# reps=1 is enough for the partition demo; >= 2 increases depth but is more
# prone to timing out inside the sandbox.
# Parameter order is [β_0, γ_0, β_1, γ_1, ...] (mixer first, then cost).
```

## Operator `SparsePauliOp`

```python
from qiskit.quantum_info import SparsePauliOp
# Construct with .from_list(...) — do not call SparsePauliOp(...) directly;
# the latter's signature requires the two positional arguments (data, coeffs),
# and passing a list will raise TypeError.
op = SparsePauliOp.from_list([("II", -0.3), ("ZZ", 0.1), ("XX", 0.2)])
# .num_qubits is the number of qubits the operator acts on.
```

`SparsePauliOp.to_list()` returns `[(pauli_str, complex), ...]` — **the
coefficients are `complex`**, even for Hermitian operators where the imaginary
part is zero. To write to JSON (e.g. the `instance.pauli_terms` field required
by cross-check), convert to real first:

```python
pauli_terms = [[s, float(c.real)] for s, c in op.to_list()]
```

## Expectation values — **prefer `Statevector.expectation_value` (much faster)**

For N ≤ ~20 qubits and single-evaluation cost-function scenarios (a single
parameter point of the QAOA / VQE energy), **`Statevector(qc).expectation_value(op)`
is 5–10x faster than `StatevectorEstimator`** (the PUB interface adds
observable coercion + bindings_array validation + result wrapping overhead;
`Statevector` goes straight through numpy evolution):

```python
from qiskit.quantum_info import Statevector

def cost(params):
    bound = ansatz.assign_parameters(params)
    sv = Statevector(bound)                  # direct evolution, no PUB overhead
    return float(sv.expectation_value(op).real)
```

In partition mode, where each block runs 193 times, this overhead is
multiplied by 193 — a per-block, per-estimator call at the seconds scale
makes the total run six hours; switching to `Statevector.expectation_value`
typically brings per-block down to ~10 seconds and the total run to about
one hour.

**Only** use `StatevectorEstimator` when you need the PUB interface for
batching (computing multiple `(circuit, op, params)` combinations at once)
or want to swap in `SamplerV2` / a real-hardware estimator:

```python
from qiskit.primitives import StatevectorEstimator
estimator = StatevectorEstimator()           # does not accept a backend argument
# PUB format (circuit, observable, parameter_values); run() takes a list of PUBs
result = estimator.run([(ansatz, op, params)]).result()
expectation = float(result[0].data.evs.real) # evs may be complex; take .real
```

**The operator and the circuit must have the same qubit count** (this applies
to both paths): for an `N`-qubit problem, every `SparsePauliOp` Pauli string
must have length `N` and match `ansatz.num_qubits`. Otherwise
`StatevectorEstimator` raises `ValueError: The number of qubits of the
circuit (...) does not match the number of qubits of the ...-th observable`,
and `Statevector.expectation_value` raises a similar qubit-count mismatch
error. Compute the required string length from `ansatz.num_qubits` before
building the operator.

## Sampling `StatevectorSampler`

```python
from qiskit.primitives import StatevectorSampler
sampler = StatevectorSampler()
result = sampler.run([(circuit, params)]).result()
counts = result[0].data.meas.get_counts()    # the default measurement register name is "meas"
```

## Parameter binding: do not mutate `circuit.data`

Wrong: `ansatz.data[0] = params` — raises `ValueError: not enough values to unpack`.

Two correct ways to bind parameters:

1. **Preferred**: pass `params` as the third element of an Estimator/Sampler
   PUB (see above).
2. If you need the bound circuit object itself:

```python
bound = ansatz.assign_parameters(params)     # returns a new QuantumCircuit
```

## Standard wiring of `scipy.optimize.minimize` with an estimator

```python
from scipy.optimize import minimize
import numpy as np

def cost(params):
    result = estimator.run([(ansatz, op, params)]).result()
    return float(result[0].data.evs)

x0 = np.zeros(ansatz.num_parameters)
res = minimize(cost, x0, method="COBYLA", options={"maxiter": 200})
# res.fun is the optimal objective value; res.x are the optimal parameters
```

To maximise a quantity, negate it: `def cost(params): return -metric(params)`.

## Building quantum circuits

```python
from qiskit import QuantumCircuit
qc = QuantumCircuit(num_qubits)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()                             # the default measurement register name is "meas"
```
