// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * ChatMessage component.
 * Renders a single chat bubble; `kind` selects the styling and layout for user, agent and system messages.
 */
import { ReactNode } from "react";

/** Message source: user, agent (AI) or system (system notice). */
export type ChatKind = "user" | "agent" | "system";

/** Props for ChatMessage: `kind` selects the styling, `text` is the plain text body, `children` allows embedding rich content such as a SolutionCard. */
export interface ChatMessageProps {
  kind: ChatKind;
  text?: string;
  children?: ReactNode;
}

/** Avatar emoji map keyed by message kind. */
const AVATAR: Record<ChatKind, string> = {
  agent: "🤖",
  user: "👤",
  system: "⚙",
};

/**
 * Single chat bubble component.
 * System messages render centered as a notice bar; user messages are right-aligned;
 * agent messages are left-aligned with a gradient avatar.
 */
export function ChatMessage({ kind, text, children }: ChatMessageProps) {
  if (kind === "system") {
    return (
      <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-center text-xs text-blue-700">
        {text}
        {children}
      </div>
    );
  }

  const isUser = kind === "user";
  return (
    <div className={`flex gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-[10px] text-[15px] ${
          isUser
            ? "border border-slate-200 bg-slate-100 text-slate-600"
            : "bg-gradient-to-br from-blue-600 to-cyan-500 text-white shadow-sm"
        }`}
      >
        {AVATAR[kind]}
      </div>
      <div
        className={`max-w-[340px] rounded-xl px-[15px] py-[11px] text-[13px] leading-relaxed shadow-sm ${
          isUser
            ? "rounded-br-sm bg-blue-600 text-white"
            : "rounded-bl-sm border border-slate-200 bg-slate-50 text-slate-900"
        }`}
      >
        {text && <p className="whitespace-pre-wrap">{text}</p>}
        {children}
      </div>
    </div>
  );
}
