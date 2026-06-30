/**
 * TraceEventDetail component tests: verifies that selecting different stage
 * records shows the corresponding fields, and that an empty-state hint is
 * shown when no record is selected.
 */
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { TraceEventDetail } from "../../src/components/TraceEventDetail";
import { fakeFullTrace } from "../../src/test/handlers";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** TraceEventDetail: covers stage detail, artifact display and empty-selection hint. */
describe("TraceEventDetail", () => {
  // analyze stage record (id=2): should show the stage name, LLM model and duration (5000 ms).
  it("renders LLM model + duration for a stage", () => {
    renderWithI18n(<TraceEventDetail trace={fakeFullTrace} selectedId={2} />, "zh");
    expect(screen.getByText(/量子机会分析/)).toBeInTheDocument();
    expect(screen.getByText(/claude-opus-4-7/)).toBeInTheDocument();
    expect(screen.getByText(/5000/)).toBeInTheDocument();
  });

  // blueprint stage record (id=3): should render the artifact collapsible block.
  it("renders the artifact block for a stage", () => {
    renderWithI18n(<TraceEventDetail trace={fakeFullTrace} selectedId={3} />, "zh");
    expect(screen.getByText(/混合蓝图/)).toBeInTheDocument();
    expect(screen.getByText("产物")).toBeInTheDocument();
  });

  // When selectedId is null: should prompt the user to pick a stage from the timeline.
  it("renders empty hint when nothing is selected", () => {
    renderWithI18n(<TraceEventDetail trace={fakeFullTrace} selectedId={null} />, "zh");
    expect(screen.getByText(/从阶段时间线选择/)).toBeInTheDocument();
  });

  // English: empty state should show English empty-state hint
  it("renders the empty-state hint in English when lang=en", () => {
    renderWithI18n(<TraceEventDetail trace={fakeFullTrace} selectedId={null} />, "en");
    expect(
      screen.getByText("Select a stage from the timeline to see details."),
    ).toBeInTheDocument();
  });

  // English: stage with id=2 should show English labels
  it("renders English labels for a stage", () => {
    renderWithI18n(<TraceEventDetail trace={fakeFullTrace} selectedId={2} />, "en");
    expect(screen.getByText("Artifact")).toBeInTheDocument();
    expect(screen.getByText("LLM input")).toBeInTheDocument();
  });
});
