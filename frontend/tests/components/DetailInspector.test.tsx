/**
 * DetailInspector component tests: verifies the right-hand detail panel
 * across three selection states — nothing selected, a DAG node selected,
 * and a trace event selected.
 */
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { DetailInspector } from "../../src/components/DetailInspector";
import { fakeFullTrace } from "../../src/test/handlers";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** DetailInspector: covers no-selection, DAG-node-selected, trace-event-selected states. */
describe("DetailInspector", () => {
  // No selection: should show the hint prompting the user to click a node or event.
  it("shows a hint when nothing is selected", () => {
    renderWithI18n(<DetailInspector trace={fakeFullTrace} selected={null} onClose={() => {}} />, "zh");
    expect(screen.getByText(/点击工作流节点或阶段时间线/)).toBeInTheDocument();
  });

  // DAG node q1 selected: the panel should display its name (VQE kernel).
  it("shows a DAG node's name when a node is selected", () => {
    renderWithI18n(
      <DetailInspector
        trace={fakeFullTrace}
        selected={{ kind: "node", id: "q1" }}
        onClose={() => {}}
      />,
      "zh"
    );
    expect(screen.getByText(/VQE 内核/)).toBeInTheDocument();
  });

  // Stage event selected (analyze stage, id=2): the panel should display the
  // LLM model among other details.
  it("shows stage detail when an event is selected", () => {
    renderWithI18n(
      <DetailInspector
        trace={fakeFullTrace}
        selected={{ kind: "event", ref: 2 }}
        onClose={() => {}}
      />,
      "zh"
    );
    expect(screen.getByText(/claude-opus-4-7/)).toBeInTheDocument();
  });

  // English: null selected → English hint text
  it("shows English hint when nothing is selected (en)", () => {
    renderWithI18n(<DetailInspector trace={fakeFullTrace} selected={null} onClose={() => {}} />, "en");
    expect(screen.getByText(/Click a workflow node/)).toBeInTheDocument();
  });

  // Selecting the quantum node q1: the panel should display kind, inputs and outputs.
  it("shows node kind, inputs and outputs when a quantum node is selected", () => {
    renderWithI18n(
      <DetailInspector
        trace={fakeFullTrace}
        selected={{ kind: "node", id: "q1" }}
        onClose={() => {}}
      />,
      "zh"
    );
    // In fakeFullTrace q1 is the quantum node, name="VQE 内核",
    // inputs=["hamiltonian"], outputs=["ground_state_energy"].
    expect(screen.getByText("VQE 内核")).toBeInTheDocument();
    expect(screen.getByText(/量子|quantum/i)).toBeInTheDocument();  // kind label
    expect(screen.getByText(/hamiltonian/)).toBeInTheDocument();    // input
    expect(screen.getByText(/ground_state_energy/)).toBeInTheDocument();  // output
  });
});
