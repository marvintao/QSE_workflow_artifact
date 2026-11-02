// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * ChatMessage component tests: verifies render behavior for the three message
 * kinds (user / agent / system) and the case where an agent message wraps
 * children (used for rich content such as the solution card).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatMessage } from "../../src/components/ChatMessage";

/** ChatMessage: covers the three message roles and the children-nesting case. */
describe("ChatMessage", () => {
  // User message: the text content should be rendered verbatim on the page.
  it("renders a user message with its text", () => {
    render(<ChatMessage kind="user" text="Compute H2 ground state energy" />);
    expect(screen.getByText("Compute H2 ground state energy")).toBeInTheDocument();
  });

  // Agent message: text content should render correctly.
  it("renders an agent message", () => {
    render(<ChatMessage kind="agent" text="Solution ready" />);
    expect(screen.getByText("Solution ready")).toBeInTheDocument();
  });

  // System message (commonly used for error notices): text content should render correctly.
  it("renders a system message", () => {
    render(<ChatMessage kind="system" text="Pipeline failed: boom" />);
    expect(screen.getByText("Pipeline failed: boom")).toBeInTheDocument();
  });

  // Rich-content case: when an agent message is given children, the child
  // elements (e.g. solution card) should render.
  it("renders children inside an agent message (for cards)", () => {
    render(
      <ChatMessage kind="agent">
        <div>card content</div>
      </ChatMessage>
    );
    expect(screen.getByText("card content")).toBeInTheDocument();
  });
});
