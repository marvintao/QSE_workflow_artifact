// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import App from "../src/App";
import { renderWithI18n } from "../src/test/renderWithI18n";

/** Smoke test: verifies the app shell renders in both zh and en. */
describe("App shell", () => {
  it("renders header, chat greeting, and the empty workflow panel (zh)", () => {
    renderWithI18n(<App />, "zh");
    expect(screen.getByText("量子工作流平台")).toBeInTheDocument();
    expect(screen.getByText("等待生成工作流")).toBeInTheDocument();
  });

  it("renders the header in English when lang=en", () => {
    renderWithI18n(<App />, "en");
    expect(screen.getByText("Quantum Workflow Platform")).toBeInTheDocument();
  });
});
