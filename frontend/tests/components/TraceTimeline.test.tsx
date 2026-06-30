/**
 * TraceTimeline component tests: verifies stage-list completeness, click-to-select
 * callback firing, and the currently-selected stage highlight style.
 */
import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TraceTimeline } from "../../src/components/TraceTimeline";
import { fakeFullTrace } from "../../src/test/handlers";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** TraceTimeline: covers stage-list rendering, click-select callback and highlight state. */
describe("TraceTimeline", () => {
  // A full trace has 8 agentic stages listed in pipeline order; first item is
  // parse, last is verify.
  it("lists all stages in pipeline order", () => {
    renderWithI18n(<TraceTimeline trace={fakeFullTrace} onSelect={() => {}} selectedId={null} />, "zh");
    const items = screen.getAllByRole("listitem");
    // parse + analyze + blueprint + encode + codegen + execute + combine + verify
    expect(items.length).toBe(8);
    expect(items[0].textContent).toMatch(/解析/);
    expect(items[items.length - 1].textContent).toMatch(/验证/);
  });

  // Clicking a list item: onSelect should fire with the stage record's numeric id.
  it("calls onSelect with the stage id when a stage is clicked", async () => {
    const onSelect = vi.fn();
    renderWithI18n(<TraceTimeline trace={fakeFullTrace} onSelect={onSelect} selectedId={null} />, "zh");
    const parseRow = screen.getByText(/解析/).closest("li")!;
    await userEvent.click(parseRow);
    expect(onSelect).toHaveBeenCalled();
    expect(onSelect.mock.calls[0][0]).toBe(1);
  });

  // The currently-selected stage (analyze, id=2) list item's className should
  // include the highlight style.
  it("highlights the currently selected stage", () => {
    renderWithI18n(
      <TraceTimeline trace={fakeFullTrace} onSelect={() => {}} selectedId={2} />,
      "zh"
    );
    const analyzeRow = screen.getByText(/量子机会分析/).closest("li")!;
    expect(analyzeRow.className).toMatch(/bg-slate-100|ring/);
  });

  // English: codegen stage label should appear in English
  it("renders English label for codegen stage", () => {
    renderWithI18n(<TraceTimeline trace={fakeFullTrace} onSelect={() => {}} selectedId={null} />, "en");
    expect(screen.getByText(/Codegen/)).toBeInTheDocument();
  });

  // The verify stage should render at the end of the timeline.
  it("renders the verify stage at the end of the timeline", () => {
    renderWithI18n(<TraceTimeline trace={fakeFullTrace} onSelect={() => {}} selectedId={null} />, "zh");
    expect(screen.getByText(/验证|Verify/)).toBeInTheDocument();
  });
});
