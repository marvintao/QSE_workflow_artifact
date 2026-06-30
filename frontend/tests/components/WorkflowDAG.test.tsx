/**
 * WorkflowDAG component tests: verifies DAG node rendering, the placeholder
 * shown when there is no workflow stage data, and that onNodeClick is fired
 * with the node id when a node is clicked.
 */
import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { WorkflowDAG } from "../../src/components/WorkflowDAG";
import { fakeFullTrace } from "../../src/test/handlers";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** WorkflowDAG: covers node rendering, no-data placeholder and click callback. */
describe("WorkflowDAG", () => {
  // All three workflow nodes (build Hamiltonian / VQE kernel / report results)
  // should render.
  it("renders one node per workflow DAG node", () => {
    renderWithI18n(<WorkflowDAG trace={fakeFullTrace} />, "zh");
    expect(screen.getByText(/构造哈密顿量/)).toBeInTheDocument();
    expect(screen.getByText(/VQE 内核/)).toBeInTheDocument();
    expect(screen.getByText(/结果汇报/)).toBeInTheDocument();
  });

  // With the blueprint stage filtered out: the DAG cannot be built, so the
  // empty-state placeholder text (zh) should render.
  it("renders a placeholder when no workflow stage exists", () => {
    const empty = {
      ...fakeFullTrace,
      stages: fakeFullTrace.stages.filter((s) => s.stage !== "blueprint"),
    };
    renderWithI18n(<WorkflowDAG trace={empty} />, "zh");
    expect(screen.getByText(/暂无工作流/)).toBeInTheDocument();
  });

  // English mode: lang=en should render the English placeholder text.
  it("renders English empty state in en mode", () => {
    const empty = {
      ...fakeFullTrace,
      stages: fakeFullTrace.stages.filter((s) => s.stage !== "blueprint"),
    };
    renderWithI18n(<WorkflowDAG trace={empty} />, "en");
    expect(screen.getByText(/no workflow available/i)).toBeInTheDocument();
  });

  // Node kind labels should be visible: at least one classical and one quantum label.
  it("displays the kind label on each node", () => {
    renderWithI18n(<WorkflowDAG trace={fakeFullTrace} />, "zh");
    // fakeFullTrace has 2 classical nodes + 1 quantum node
    expect(screen.getAllByText(/经典|classical/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/量子|quantum/i).length).toBeGreaterThanOrEqual(1);
  });

  // Clicking the VQE-kernel node: onNodeClick should fire with the node id (string).
  it("calls onNodeClick with the node id when a node is clicked", () => {
    const onNodeClick = vi.fn();
    renderWithI18n(<WorkflowDAG trace={fakeFullTrace} onNodeClick={onNodeClick} />, "zh");
    const label = screen.getByText(/VQE 内核/);
    fireEvent.click(label.closest(".react-flow__node") ?? label);
    expect(onNodeClick).toHaveBeenCalled();
    expect(typeof onNodeClick.mock.calls[0][0]).toBe("string");
  });
});
