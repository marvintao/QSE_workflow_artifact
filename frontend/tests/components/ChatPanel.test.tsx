// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * ChatPanel component tests: verifies message list rendering, input submission,
 * empty-input guard, loading-state disabling and quick-example button
 * fill-in behavior. Model selection is driven by backend/config so ChatPanel
 * no longer renders ModelSelector.
 */
import { describe, it, expect, vi } from "vitest";
import { screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "../../src/components/ChatPanel";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** ChatPanel: covers message list, submit logic, loading state and quick examples. */
describe("ChatPanel", () => {
  // With a non-empty messages array the panel should render every message bubble.
  it("renders given messages", () => {
    renderWithI18n(
      <ChatPanel
        messages={[
          { kind: "agent", text: "Hello" },
          { kind: "user", text: "Compute H2 ground state energy" },
        ]}
        loading={false}
        onSubmit={() => {}}
      />,
      "zh"
    );
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Compute H2 ground state energy")).toBeInTheDocument();
  });

  // Normal submit: after typing text and clicking send, onSubmit should fire
  // once with that text.
  it("submits the typed requirement", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithI18n(<ChatPanel messages={[]} loading={false} onSubmit={onSubmit} />, "zh");
    await act(async () => {
      await user.type(screen.getByRole("textbox"), "Compute H2 ground state energy");
      await user.click(screen.getByRole("button", { name: "发送" }));
    });
    expect(onSubmit).toHaveBeenCalledWith("Compute H2 ground state energy");
  });

  // Empty-input guard: with an empty input, clicking send should not fire onSubmit.
  it("does not submit empty input", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithI18n(<ChatPanel messages={[]} loading={false} onSubmit={onSubmit} />, "zh");
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "发送" }));
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  // Loading state: loading=true should show the "thinking" indicator and disable send.
  it("shows the thinking indicator and disables send while loading", () => {
    renderWithI18n(<ChatPanel messages={[]} loading={true} onSubmit={() => {}} />, "zh");
    expect(screen.getByText("思考中…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成中…" })).toBeDisabled();
  });

  // Quick examples: clicking any example button then send should fire onSubmit
  // once with a non-empty payload.
  it("fills the input from a quick-example button", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithI18n(<ChatPanel messages={[]} loading={false} onSubmit={onSubmit} />, "zh");
    const quick = screen.getAllByTestId("quick-example");
    expect(quick.length).toBe(4);
    await act(async () => {
      await user.click(quick[0]);
    });
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "发送" }));
    });
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("计算氢分子 H₂ 在键长 0.74 Å 时的基态能量");
  });

  // English mode: lang=en should render the send button label in English.
  it("renders the send button in English when lang=en", () => {
    renderWithI18n(<ChatPanel messages={[]} loading={false} onSubmit={() => {}} />, "en");
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });

  // Translation-key messages: a textKey app-generated message should render
  // via t() into the translated string.
  it("renders an app message given by translation key", () => {
    renderWithI18n(
      <ChatPanel
        messages={[{ kind: "agent", textKey: "chat.solutionReady" }]}
        loading={false}
        onSubmit={() => {}}
      />,
      "zh",
    );
    expect(screen.getByText("方案已生成,详见右侧。")).toBeInTheDocument();
  });

  // Upload button + file picker → textarea is populated with the file contents.
  it("loads file contents into the input on file upload", async () => {
    renderWithI18n(
      <ChatPanel messages={[]} loading={false} onSubmit={() => {}} />,
      "zh",
    );
    // Button is visible.
    expect(screen.getByTestId("file-upload-btn")).toBeInTheDocument();
    const input = screen.getByTestId("file-upload-input") as HTMLInputElement;
    const file = new File(
      ["# Hello\nLine 2"], "req.txt", { type: "text/plain" });
    // jsdom does not implement real File.text(); stub it.
    Object.defineProperty(file, "text", {
      value: () => Promise.resolve("# Hello\nLine 2"),
    });
    await act(async () => {
      // Directly fire change (jsdom simulates file selection).
      Object.defineProperty(input, "files", { value: [file] });
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.value).toBe("# Hello\nLine 2");
    expect(screen.getByTestId("file-upload-name").textContent)
      .toContain("req.txt");
  });

  // No longer renders ModelSelector (model selection lives in backend/config).
  it("does not render any model selector", () => {
    renderWithI18n(
      <ChatPanel messages={[]} loading={false} onSubmit={() => {}} />,
      "zh",
    );
    expect(screen.queryByTestId("model-selector")).toBeNull();
  });
});
