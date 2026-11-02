// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * StatsBar component tests: verifies the four stat labels (stage count,
 * qubit count, computed value, wall-clock duration) render correctly,
 * numeric values compute as expected, and a placeholder shows when data
 * is missing.
 */
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { StatsBar } from "../../src/components/StatsBar";
import { fakeFullTrace } from "../../src/test/handlers";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** StatsBar: covers label rendering, value computation and missing-data placeholders. */
describe("StatsBar", () => {
  // The four stat labels (zh dictionary strings) should all render in zh mode.
  it("renders the four Chinese stat labels", () => {
    renderWithI18n(<StatsBar trace={fakeFullTrace} />, "zh");
    for (const label of ["阶段数", "量子比特数", "计算结果", "墙钟耗时"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  // Stage count should equal the stages array length (8: full agentic pipeline).
  it("computes the stage count", () => {
    renderWithI18n(<StatsBar trace={fakeFullTrace} />, "zh");
    expect(screen.getByText("8")).toBeInTheDocument();
  });

  // Qubit count should be 2 (reduced_qubits); computed value should display -1.137.
  it("shows qubits and value", () => {
    renderWithI18n(<StatsBar trace={fakeFullTrace} />, "zh");
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText(/-1\.137/)).toBeInTheDocument();
  });

  // When analyze and execute stages are both missing: qubit count, computed value
  // and duration should all show the em-dash placeholder.
  it("shows a dash for missing data", () => {
    const empty = {
      ...fakeFullTrace,
      stages: fakeFullTrace.stages.filter(
        (s) => s.stage !== "analyze" && s.stage !== "execute",
      ),
    };
    renderWithI18n(<StatsBar trace={empty} />, "zh");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  // English mode: lang=en should render stat labels in English.
  it("renders English stat labels in en mode", () => {
    renderWithI18n(<StatsBar trace={fakeFullTrace} />, "en");
    expect(screen.getByText("Stages")).toBeInTheDocument();
  });
});
