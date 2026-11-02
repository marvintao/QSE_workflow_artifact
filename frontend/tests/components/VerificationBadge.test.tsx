// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/** VerificationBadge unit tests. */
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithI18n } from "../../src/test/renderWithI18n";
import { VerificationBadge } from "../../src/components/VerificationBadge";

describe("VerificationBadge", () => {
  it("renders nothing when status is null", () => {
    const { container } = renderWithI18n(<VerificationBadge status={null} />, "zh");
    expect(container).toBeEmptyDOMElement();
  });

  it("renders cross_checked with green styling", () => {
    renderWithI18n(<VerificationBadge status="cross_checked" />, "zh");
    expect(screen.getByText("已交叉验证")).toBeInTheDocument();
  });

  it("renders off_spec with distinct label", () => {
    renderWithI18n(<VerificationBadge status="off_spec" />, "zh");
    // zh.verification.offSpec = "代码解错了问题"
    expect(screen.getByText("代码解错了问题")).toBeInTheDocument();
  });
});
