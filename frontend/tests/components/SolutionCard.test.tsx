/**
 * SolutionCard component tests: verifies algorithm, qubit-count and execution
 * result display, the empty state when no execution data is present, and the
 * panel rendering when there is no quantum benefit.
 */
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { SolutionCard } from "../../src/components/SolutionCard";
import { fakeFullTrace } from "../../src/test/handlers";
import { renderWithI18n } from "../../src/test/renderWithI18n";
import type { FullTrace } from "../../src/api/types";

/** SolutionCard: covers algorithm, qubits, execution result and no-result empty state. */
describe("SolutionCard", () => {
  // Should display the solution heading, algorithm (VQE) and the LLM-provided rationale.
  it("shows the solution approach and rationale", () => {
    renderWithI18n(<SolutionCard trace={fakeFullTrace} />, "zh");
    expect(screen.getByText(/算法:/)).toBeInTheDocument();
    expect(screen.getByText(/VQE/i)).toBeInTheDocument();
    expect(screen.getByText(/适配本征值最小化/)).toBeInTheDocument();
  });

  // Qubit count should be read from quantum_kernel.reduced_qubits (2 in this fixture).
  it("shows qubit count", () => {
    renderWithI18n(<SolutionCard trace={fakeFullTrace} />, "zh");
    expect(screen.getByText(/2 量子比特/)).toBeInTheDocument();
  });

  // Execution result: should show the computed value (-1.137) and a success status.
  it("shows the computed value and status", () => {
    renderWithI18n(<SolutionCard trace={fakeFullTrace} />, "zh");
    expect(screen.getByText(/-1\.137/)).toBeInTheDocument();
    expect(screen.getByText(/成功/)).toBeInTheDocument();
  });

  // When no execute stage record exists, the "no execution result" placeholder
  // (zh dictionary string) should be displayed.
  it("handles a trace with no execution result", () => {
    const empty = {
      ...fakeFullTrace,
      stages: fakeFullTrace.stages.filter((s) => s.stage !== "execute"),
    };
    renderWithI18n(<SolutionCard trace={empty} />, "zh");
    expect(screen.getByText(/暂无执行结果/)).toBeInTheDocument();
  });

  // English mode: lang=en should render labels in English.
  it("renders labels in English when lang=en", () => {
    renderWithI18n(<SolutionCard trace={fakeFullTrace} />, "en");
    expect(screen.getByText(/Algorithm:/)).toBeInTheDocument();
    expect(screen.getByText(/2 qubits/)).toBeInTheDocument();
  });

  // When quantum_kernel is null: should render the no-quantum-benefit panel
  // along with the reason text.
  it("renders no-quantum-part panel when quantum_kernel is null", () => {
    const noKernelTrace: FullTrace = {
      ...fakeFullTrace,
      stages: fakeFullTrace.stages.map((s) =>
        s.stage === "analyze"
          ? {
              ...s,
              artifact: {
                decomposition: [
                  { name: "Solve", description: "Linear programming", disposition: "classical" },
                ],
                quantum_kernel: null,
                no_quantum_reason: "Problem is pure linear programming, no quantum benefit",
              },
            }
          : s,
      ),
    };
    // Reuse the file's existing render pattern.
    renderWithI18n(<SolutionCard trace={noKernelTrace} />, "zh");
    expect(screen.getAllByText(/无量子增益|No quantum benefit/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/pure linear programming/)).toBeInTheDocument();
  });

  // needs_reduction=true: should show reduced/full qubit interpolation and a
  // reduction_note panel.
  it("renders reduction info (reduced/full qubits + reduction note) when needs_reduction is true", () => {
    const reducedTrace: FullTrace = {
      ...fakeFullTrace,
      stages: fakeFullTrace.stages.map((s) =>
        s.stage === "analyze"
          ? {
              ...s,
              artifact: {
                decomposition: [
                  { name: "Combinatorial optimization", description: "QUBO minimization", disposition: "quantum" },
                ],
                quantum_kernel: {
                  algorithm: "QAOA",
                  algorithm_rationale: "r",
                  subproblem: "Asset selection QUBO",
                  io_interface: "i",
                  full_scale_qubits: 500,
                  feasible_qubits: 24,
                  needs_reduction: true,
                  reduced_qubits: 16,
                  reduction_note: "Extract a 16-asset sub-problem",
                },
                no_quantum_reason: null,
              },
            }
          : s,
      ),
    };
    renderWithI18n(<SolutionCard trace={reducedTrace} />, "zh");
    // opportunity.scale = "{reduced} 量子比特(全规模 {full})"
    expect(screen.getByText(/16 量子比特.*500/)).toBeInTheDocument();
    // amber reduction_note panel
    expect(screen.getByText(/Extract a 16-asset sub-problem/)).toBeInTheDocument();
  });
});
