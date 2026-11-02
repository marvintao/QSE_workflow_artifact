// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * WorkflowPanel component tests: verifies the empty-state placeholder when
 * no trace is given, and the combined rendering of pipeline bar, DAG and
 * stats when a trace is present.
 */
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { WorkflowPanel } from "../../src/components/WorkflowPanel";
import { fakeFullTrace } from "../../src/test/handlers";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** WorkflowPanel: covers the empty-trace placeholder and the full-trace combined render. */
describe("WorkflowPanel", () => {
  // With trace=null: the "waiting for workflow" placeholder (zh) should render.
  it("shows the empty state when no trace", () => {
    renderWithI18n(
      <WorkflowPanel trace={null} onSelectNode={() => {}} onSelectEvent={() => {}}
        selectedEventId={null} />,
      "zh"
    );
    expect(screen.getByText("等待生成工作流")).toBeInTheDocument();
  });

  // With a full trace: pipeline-stage label, DAG node names and a stats label
  // should all appear simultaneously.
  it("renders pipeline bar, DAG, stats and code for a trace", () => {
    renderWithI18n(
      <WorkflowPanel trace={fakeFullTrace} onSelectNode={() => {}}
        onSelectEvent={() => {}} selectedEventId={null} />,
      "zh"
    );
    // "解析需求" appears in both the pipeline status bar and the stage timeline,
    // so we use getAllByText to assert it shows at least once.
    expect(screen.getAllByText("解析需求").length).toBeGreaterThan(0);
    expect(screen.getByText(/VQE 内核|VQE/)).toBeInTheDocument();
    expect(screen.getByText("阶段数")).toBeInTheDocument();
  });

  // English mode: lang=en should render the English empty state.
  it("renders English empty state in en mode", () => {
    renderWithI18n(
      <WorkflowPanel trace={null} onSelectNode={() => {}} onSelectEvent={() => {}}
        selectedEventId={null} />,
      "en"
    );
    expect(screen.getByText("Waiting for workflow")).toBeInTheDocument();
  });
});
