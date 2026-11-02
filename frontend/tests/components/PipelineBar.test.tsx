// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * PipelineBar component tests: verifies the 8-stage agentic pipeline labels
 * (including verify), completed state, running highlight, and the count text.
 */
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { PipelineBar } from "../../src/components/PipelineBar";
import { fakeFullTrace } from "../../src/test/handlers";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** PipelineBar: covers all 8 stages in STAGE_ORDER (including the verify stage). */
describe("PipelineBar", () => {
  // 8 stage names (parse / analyze / blueprint / encode / codegen / execute / combine / verify).
  it("renders the eight Chinese stage labels", () => {
    renderWithI18n(<PipelineBar trace={fakeFullTrace} />, "zh");
    for (const label of ["解析需求", "量子机会分析", "混合蓝图",
                          "分解编码", "生成代码", "执行", "合并结果",
                          "验证"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  // Full trace: all 9 step className should contain "emerald" (completed-green).
  // STAGE_ORDER now includes global_review; fakeFullTrace has no global_review row,
  // so that badge still renders but state=pending (not done).
  it("marks all stages that appear in trace as done", () => {
    renderWithI18n(<PipelineBar trace={fakeFullTrace} />, "zh");
    const steps = screen.getAllByTestId("pipeline-step");
    // 9 badges (parse/analyze/blueprint/encode/codegen/global_review/
    // execute/combine/verify) — global_review lives inside the loop frame, others outside.
    expect(steps.length).toBe(9);
    // All 8 except global_review should be done (fakeFullTrace has no global_review).
    const cgrBadge = steps.find((s) => s.getAttribute("data-stage") === "global_review");
    expect(cgrBadge?.getAttribute("data-state")).toBe("pending");
    const nonReview = steps.filter((s) => s.getAttribute("data-stage") !== "global_review");
    expect(nonReview.every((s) => s.className.includes("emerald"))).toBe(true);
  });

  // Partial trace (missing codegen / execute) → codegen and execute badges
  // should not show the completed styling.
  it("marks only completed stages done for a partial trace", () => {
    const partial = {
      ...fakeFullTrace,
      stages: fakeFullTrace.stages.filter(
        (s) => s.stage !== "codegen" && s.stage !== "execute",
      ),
    };
    renderWithI18n(<PipelineBar trace={partial} />, "zh");
    const steps = screen.getAllByTestId("pipeline-step");
    // STAGE_ORDER: parse/analyze/blueprint/encode/codegen/global_review/execute/combine/verify
    const byStage = (s: string) =>
      steps.find((el) => el.getAttribute("data-stage") === s);
    expect(byStage("codegen")?.className.includes("emerald")).toBe(false);
    expect(byStage("execute")?.className.includes("emerald")).toBe(false);
  });

  // English mode: lang=en should render stage labels in English.
  it("renders English stage labels in en mode", () => {
    renderWithI18n(<PipelineBar trace={fakeFullTrace} />, "en");
    expect(screen.getByText("Parse")).toBeInTheDocument();
    expect(screen.getByText("Verify")).toBeInTheDocument();
  });

  // In-flight (final_status=null): the first incomplete stage should be running,
  // the rest pending.
  it("marks the first missing stage as running while pipeline is in-flight", () => {
    const partial = {
      ...fakeFullTrace,
      request: { ...fakeFullTrace.request, final_status: null,
                 verification_status: null },
      stages: fakeFullTrace.stages.filter(
        (s) => ["parse", "analyze", "blueprint"].includes(s.stage)),
    };
    renderWithI18n(<PipelineBar trace={partial} />, "zh");
    const steps = screen.getAllByTestId("pipeline-step");
    const byStage = (s: string) =>
      steps.find((el) => el.getAttribute("data-stage") === s);
    expect(byStage("parse")?.getAttribute("data-state")).toBe("done");
    expect(byStage("analyze")?.getAttribute("data-state")).toBe("done");
    expect(byStage("blueprint")?.getAttribute("data-state")).toBe("done");
    expect(byStage("encode")?.getAttribute("data-state")).toBe("running");
    expect(byStage("codegen")?.getAttribute("data-state")).toBe("pending");
    expect(byStage("global_review")?.getAttribute("data-state")).toBe("pending");
    expect(byStage("verify")?.getAttribute("data-state")).toBe("pending");
    // Header count: 3/9 (STAGE_ORDER has 9 items including global_review).
    expect(screen.getByText("3 / 9 阶段完成")).toBeInTheDocument();
    expect(screen.getByText(/正在跑/)).toBeInTheDocument();
  });

  // After pipeline terminal state: no running highlight should remain.
  it("shows no running stage once final_status is set", () => {
    renderWithI18n(<PipelineBar trace={fakeFullTrace} />, "zh");
    const steps = screen.getAllByTestId("pipeline-step");
    expect(steps.every((s) =>
      s.getAttribute("data-state") !== "running")).toBe(true);
    expect(screen.queryByText(/正在跑/)).toBeNull();
  });

  // Review-loop sub-frame: codegen ⇄ global_review should render as a review-loop group.
  it("renders codegen ⇄ global_review as a review-loop group", () => {
    renderWithI18n(<PipelineBar trace={fakeFullTrace} />, "zh");
    const loop = screen.getByTestId("review-loop");
    expect(loop).toBeInTheDocument();
    // codegen badge sits inside the loop.
    const codegenBadge = screen.getAllByTestId("pipeline-step").find(
      (el) => el.getAttribute("data-stage") === "codegen");
    expect(codegenBadge).toBeDefined();
    expect(loop.contains(codegenBadge!)).toBe(true);
    // global_review badge also sits inside the loop.
    const grBadge = screen.getAllByTestId("pipeline-step").find(
      (el) => el.getAttribute("data-stage") === "global_review");
    expect(grBadge).toBeDefined();
    expect(loop.contains(grBadge!)).toBe(true);
    // The ⇄ symbol is inside the loop.
    expect(loop.textContent).toContain("⇄");
  });

  // Multi-round review: global_review has 2 attempts → the "2 rounds" badge shows.
  it("shows review-rounds badge when global_review attempt count > 1", () => {
    const withMultiReview = {
      ...fakeFullTrace,
      stages: [
        ...fakeFullTrace.stages,
        {
          id: 999, stage: "global_review", attempt: 1,
          llm_input: null, llm_output: null, llm_model: null,
          duration_ms: null, token_usage: null,
          artifact: { verdict: "revise", feedback: "please revise" },
          created_at: "2026-06-10T00:00:00Z",
        },
        {
          id: 1000, stage: "global_review", attempt: 2,
          llm_input: null, llm_output: null, llm_model: null,
          duration_ms: null, token_usage: null,
          artifact: { verdict: "approve", feedback: "" },
          created_at: "2026-06-10T00:00:01Z",
        },
      ],
    };
    renderWithI18n(<PipelineBar trace={withMultiReview} />, "zh");
    const rounds = screen.getByTestId("review-rounds");
    expect(rounds).toBeInTheDocument();
    expect(rounds.textContent).toMatch(/2/);
  });
});
