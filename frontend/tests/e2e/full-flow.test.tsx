// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * End-to-end integration tests: uses MSW interceptors to simulate the full
 * backend, covering the complete user journey (submit requirement → view
 * solution → inspect DAG → inspect trace event), as well as failure flow
 * and the reset-conversation feature.
 */
import { describe, it, expect, afterEach } from "vitest";
import { screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../../src/App";
import { renderWithI18n } from "../../src/test/renderWithI18n";

/** Full flow: covers submit → solution → DAG → trace-event interactions. */
describe("Full flow", () => {
  afterEach(() => localStorage.clear());

  // Main scenario: after typing a requirement, verify the solution card, DAG
  // nodes, trace timeline and detail panel all render correctly in turn.
  it("submit a requirement, see the solution card, the workflow, and inspect an event", async () => {
    renderWithI18n(<App />, "zh");
    expect(screen.getByText("量子工作流平台")).toBeInTheDocument();

    await userEvent.type(screen.getByRole("textbox"), "Compute H2 ground state energy");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByText("Compute H2 ground state energy")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/📋 量子机会分析/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText(/VQE/).length).toBeGreaterThan(0));
    expect(screen.getByText("阶段数")).toBeInTheDocument();

    // Click a DAG node → right column shows the node's detail
    const { fireEvent } = await import("@testing-library/react");
    // Find the VQE element that lives inside a react-flow node
    const vqeEls = screen.getAllByText(/VQE/);
    const dagNode = vqeEls.find((el) => el.closest(".react-flow__node") !== null) ?? vqeEls[0];
    const reactFlowNode = dagNode.closest(".react-flow__node") ?? dagNode;
    fireEvent.click(reactFlowNode);
    await waitFor(() => expect(screen.getByText(/性质:|Kind:/)).toBeInTheDocument());

    // Inspect a stage on the timeline → right column shows detail
    const solutionStage = screen
      .getAllByText(/解析需求|Parse/)
      .map((el) => el.closest("li"))
      .find((li): li is HTMLLIElement => li !== null)!;
    await userEvent.click(solutionStage);
    await waitFor(() =>
      expect(screen.getByText(/claude-opus-4-7/)).toBeInTheDocument()
    );
  });

  // Failure scenario: when raw_text is "FAIL" the backend returns 502 and the
  // frontend should surface a pipeline-failed notice.
  it("shows an error message when the pipeline fails", async () => {
    renderWithI18n(<App />, "zh");
    await userEvent.type(screen.getByRole("textbox"), "FAIL");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() =>
      expect(screen.getByText(/流水线失败/)).toBeInTheDocument()
    );
  });

  // Reset scenario: clicking the reset button clears history and the workflow
  // area goes back to the empty placeholder.
  it("reset clears the conversation", async () => {
    renderWithI18n(<App />, "zh");
    await userEvent.type(screen.getByRole("textbox"), "Compute H2 ground state energy");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => expect(screen.getByText(/📋 量子机会分析/)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "重置对话" }));
    expect(screen.queryByText("Compute H2 ground state energy")).not.toBeInTheDocument();
    expect(screen.getByText("等待生成工作流")).toBeInTheDocument();
  });

  // Language switch scenario: starts in zh, clicking the "English" button
  // flips static UI and keyed chat bubbles to English.
  it("switching to English flips static UI and keyed chat bubbles", async () => {
    const user = userEvent.setup();
    renderWithI18n(<App />, "zh");
    // starts in Chinese — static title
    expect(screen.getByText("量子工作流平台")).toBeInTheDocument();
    // keyed greeting bubble renders in Chinese before the switch
    expect(screen.getByText(/你好[!！]请描述/)).toBeInTheDocument();
    // switch to English
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "English" }));
    });
    // static title flipped
    expect(screen.getByText("Quantum Workflow Platform")).toBeInTheDocument();
    expect(screen.queryByText("量子工作流平台")).not.toBeInTheDocument();
    // the input placeholder is now English
    expect(
      screen.getByPlaceholderText("Describe your quantum computing requirement…"),
    ).toBeInTheDocument();
    // keyed greeting bubble re-rendered in English
    expect(screen.getByText(/Hello! Describe the quantum/)).toBeInTheDocument();
    // Chinese greeting bubble is gone
    expect(screen.queryByText(/你好！请描述/)).not.toBeInTheDocument();
  });
});
