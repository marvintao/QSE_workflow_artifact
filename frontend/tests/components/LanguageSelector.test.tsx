// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

import { describe, it, expect } from "vitest";
import { screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguageSelector } from "../../src/components/LanguageSelector";
import { renderWithI18n } from "../../src/test/renderWithI18n";

describe("LanguageSelector", () => {
  it("renders both language options", () => {
    renderWithI18n(<LanguageSelector />, "zh");
    expect(screen.getByRole("button", { name: "中文" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "English" })).toBeInTheDocument();
  });

  it("switching to English updates the surrounding UI language", async () => {
    const user = userEvent.setup();
    renderWithI18n(
      <div>
        <LanguageSelector />
      </div>,
      "zh",
    );
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "English" }));
    });
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "中文" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
