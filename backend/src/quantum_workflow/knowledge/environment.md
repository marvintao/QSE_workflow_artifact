# Execution Environment Facts (Qiskit 2.x)

Generated code runs in the environment below; violations will crash:

- Installed: Qiskit 2.x, qiskit-aer, numpy, scipy. No other quantum libraries.
- Not installed / removed — importing crashes: `qiskit_aqua`, `qiskit.aqua`,
  `qiskit_nature`, `qiskit_algorithms`, `qiskit_ibm_runtime`, `pyscf`,
  `openfermion`; `qiskit.opflow`, `qiskit.optimization`, `qiskit.algorithms`;
  the `Aer` object (`from qiskit import Aer`), `execute`, `assemble`,
  `QuantumInstance`, `PauliSumOp`, opflow expectation-value converters.
- Qiskit 2.x APIs to use:
  - Expectation values: `from qiskit.primitives import StatevectorEstimator`
  - Sampling: `from qiskit.primitives import StatevectorSampler`
  - Simulator backend: `from qiskit_aer import AerSimulator`
  - Variational ansatz: `from qiskit.circuit.library import efficient_su2`
  - Operators: `from qiskit.quantum_info import SparsePauliOp`
  - Classical optimizer: `from scipy.optimize import minimize`
- `StatevectorEstimator` is a pure statevector primitive and does not accept a
  `backend` argument; the PUB format is `(circuit, observable, parameter_values)`,
  and expectation values are read via `.result()[0].data.evs`.
