// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * CodeViewer component tests: verifies content rendering when code is present,
 * and the empty-state hint when code is null.
 */
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { CodeViewer } from "../../src/components/CodeViewer";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** CodeViewer: covers both the code-display and null-empty-state scenarios. */
describe("CodeViewer", () => {
  // With code present: the component should render the code text into the DOM
  // (use container.textContent to bypass <pre> matching quirks).
  it("renders code content", () => {
    const { container } = renderWithI18n(<CodeViewer code={"from qiskit import x\nprint('hi')"} />, "zh");
    expect(container.textContent).toMatch(/from qiskit/);
    expect(container.textContent).toMatch(/print/);
  });

  // When code is null: should display the "no code generated" placeholder (zh).
  it("renders empty state when code is null", () => {
    renderWithI18n(<CodeViewer code={null} />, "zh");
    expect(screen.getByText(/暂无生成代码/)).toBeInTheDocument();
  });

  // English mode: lang=en should render the English empty state.
  it("renders English empty state in en mode", () => {
    renderWithI18n(<CodeViewer code={null} />, "en");
    expect(screen.getByText("No code generated")).toBeInTheDocument();
  });
});
