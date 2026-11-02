# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""SDK-native agent loop runner — used when codegen / verify takes the SDK path.

Design: the caller provides a system prompt, a user prompt, and a list
of `@tool`-decorated MCP tools (closures over state). The runner then:
  1. create_sdk_mcp_server(tools=...) spins up an in-process MCP server.
  2. ClaudeAgentOptions(mcp_servers, allowed_tools, model, max_turns).
  3. async for msg in query(...): consume the SDK stream.
  4. An AssistantMessage (containing TextBlock + ToolUseBlock) plus the
     following UserMessage (containing ToolResultBlock; the SDK feeds
     tool results automatically) becomes one AgentRound.
  5. A ResultMessage delivers final text + usage, and ends the loop.

Tools are actually executed by the SDK calling our decorated async
functions (in-process, zero IPC), and state is shared with the main
process via closures (the stage uses these to evaluate flags like
`sandbox_ok`).
"""
import asyncio
import time
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SdkMcpTool,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    query,
)

from quantum_workflow.llm.agent_runtime import AgentRound
from quantum_workflow.llm.protocol import LLMError, ToolCall, ToolResult


def _flush_partial_round(
    rounds: list, round_no: int, thought_parts: list[str],
    pending_calls: list, round_start_ts: float,
) -> None:
    """Flush the in-progress round buffer into `rounds` before raising an exception (otherwise the last call before the error is lost)."""
    if pending_calls or thought_parts:
        rounds.append(AgentRound(
            round_number=round_no,
            thought="".join(thought_parts),
            tool_calls=list(pending_calls),
            tool_results=[],
            duration_ms=int((time.monotonic() - round_start_ts) * 1000),
            token_usage={},
        ))


class SDKAgentFailure(LLMError):
    """SDK agent ran to max_turns or the server errored, but some rounds were already buffered.

    The caller (stage_codegen / stage_verify) catches this exception and
    can persist the partial rounds into stage_trace, making the failure
    analyzable. Raising a bare LLMError would discard the rounds and
    leave rounds=0 in the trace, making post-mortem impossible.
    """
    def __init__(self, message: str, rounds: list[AgentRound],
                 usage: dict):
        super().__init__(message)
        self.rounds = rounds
        self.usage = usage


class ClaudeSDKAgentRunner:
    """Drive the SDK's built-in agent loop and convert its message stream into an AgentRound list."""

    def __init__(self, model: str, max_rounds: int):
        """Initialize.

        Args:
            model: Claude model ID (e.g. "claude-opus-4-7").
            max_rounds: Max rounds for the SDK-internal agent loop (max_turns).
        """
        self.model = model
        self.max_rounds = max_rounds

    def run(
        self, *, system: str, user: str,
        tools: list[SdkMcpTool], server_name: str = "agent",
    ) -> tuple[str | None, list[AgentRound], dict]:
        """Synchronous entry point: wraps the async run with asyncio.run."""
        return asyncio.run(self._async_run(system, user, tools, server_name))

    async def _async_run(self, system, user, tools, server_name):
        server = create_sdk_mcp_server(
            name=server_name, version="1.0.0", tools=tools)
        # SDK MCP tool names follow `mcp__<server>__<tool>`; allowed_tools is restricted to the registered set.
        allowed = [f"mcp__{server_name}__{t.name}" for t in tools]
        # Block the SDK builtin tools at the system level (Bash / Read /
        # Write / Grep / Glob / WebFetch / WebSearch / ToolSearch /
        # TodoWrite / Task, etc.). By default the SDK exposes the full
        # claude_code preset, and Opus 4.7 occasionally calls them even
        # when the prompt explicitly forbids them (in practice reqs
        # b9abf7c2 / b013268e both invoke ToolSearch on round 0).
        # Setting disallowed_tools=[...] + tools=[] explicitly blocks
        # the builtins so the LLM gets a deny instead of wasting a turn.
        builtin_blocklist = [
            "Bash", "Read", "Write", "Edit", "NotebookEdit",
            "Grep", "Glob", "WebFetch", "WebSearch", "ToolSearch",
            "TodoWrite", "Task", "Agent",
        ]

        options = ClaudeAgentOptions(
            system_prompt=system,
            model=self.model,
            max_turns=self.max_rounds,
            mcp_servers={server_name: server},
            allowed_tools=allowed,
            disallowed_tools=builtin_blocklist,
            permission_mode="bypassPermissions",
        )

        rounds: list[AgentRound] = []
        usage = {
            "input_tokens": 0, "output_tokens": 0,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
        }
        final_text: str | None = None
        # Per-round accumulators: one assistant segment (text + tool_use)
        # plus the immediately following user message's tool_result are
        # paired into a single AgentRound.
        pending_calls: list[ToolCall] = []
        round_thought_parts: list[str] = []
        round_no = 0
        round_start_ts = time.monotonic()

        async for msg in query(prompt=user, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        round_thought_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        pending_calls.append(ToolCall(
                            tool_id=block.id,
                            tool_name=block.name,
                            arguments=block.input or {},
                        ))
                self._merge_usage(usage, msg.usage)
                if msg.error:
                    # rate_limit: explicitly reported by the SDK.
                    # unknown: empirical — during OAuth-window rate
                    # limiting, the SDK marks some round of the codegen
                    # / verify agent loop as "unknown" (in many round-2
                    # reqs running for 1.5-2h this is what comes back).
                    # Both add the RATE_LIMIT marker so the batch script
                    # enters pause + 15-min ping mode.
                    from quantum_workflow.llm.claude_sdk_client import (
                        ClaudeSDKClient,
                    )
                    is_rl = msg.error in ("rate_limit", "unknown")
                    prefix = (
                        ClaudeSDKClient._RATE_LIMIT_MARKER + " "
                        if is_rl else ""
                    )
                    # On failure also flush the partial round buffer
                    # into `rounds` so post-mortems can see the LLM's
                    # last tool call / text before the error.
                    _flush_partial_round(
                        rounds, round_no, round_thought_parts,
                        pending_calls, round_start_ts)
                    raise SDKAgentFailure(
                        f"{prefix}SDK AssistantMessage error: {msg.error}",
                        rounds=rounds, usage=usage,
                    )
            elif isinstance(msg, UserMessage):
                results: list[ToolResult] = []
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        out = ""
                        if isinstance(block.content, list):
                            for c in block.content:
                                if (isinstance(c, dict)
                                        and c.get("type") == "text"):
                                    out += c.get("text", "")
                        elif isinstance(block.content, str):
                            out = block.content
                        # Tool name comes from the matching pending_calls entry (the SDK does not repeat it in the result).
                        name = next(
                            (tc.tool_name for tc in pending_calls
                             if tc.tool_id == block.tool_use_id),
                            "",
                        )
                        results.append(ToolResult(
                            tool_id=block.tool_use_id,
                            tool_name=name,
                            output=out,
                        ))
                if pending_calls or results:
                    round_end_ts = time.monotonic()
                    rounds.append(AgentRound(
                        round_number=round_no,
                        thought="".join(round_thought_parts),
                        tool_calls=list(pending_calls),
                        tool_results=results,
                        duration_ms=int(
                            (round_end_ts - round_start_ts) * 1000),
                        token_usage={},
                    ))
                    round_no += 1
                    pending_calls = []
                    round_thought_parts = []
                    round_start_ts = round_end_ts
            elif isinstance(msg, ResultMessage):
                if msg.is_error:
                    err = "; ".join(msg.errors or []) or msg.subtype
                    # Failed ResultMessage (typical: "Reached maximum
                    # number of turns") — carry the rounds back instead
                    # of raising naked and losing the data.
                    self._merge_usage(usage, msg.usage)
                    _flush_partial_round(
                        rounds, round_no, round_thought_parts,
                        pending_calls, round_start_ts)
                    raise SDKAgentFailure(
                        f"SDK agent error: {err}",
                        rounds=rounds, usage=usage,
                    )
                final_text = msg.result
                self._merge_usage(usage, msg.usage)
                # ResultMessage is terminal; exit the loop.
                break

        # Trailing partial round (the assistant emitted text but no
        # user follow-up arrived, e.g. final answer without a tool
        # call) — record one final row.
        if pending_calls or round_thought_parts:
            rounds.append(AgentRound(
                round_number=round_no,
                thought="".join(round_thought_parts),
                tool_calls=list(pending_calls),
                tool_results=[],
                duration_ms=int((time.monotonic() - round_start_ts) * 1000),
                token_usage={},
            ))

        return final_text, rounds, usage

    @staticmethod
    def _merge_usage(target: dict, src: dict | None) -> None:
        if not src:
            return
        for k in ("input_tokens", "output_tokens",
                  "cache_creation_input_tokens",
                  "cache_read_input_tokens"):
            target[k] += int(src.get(k, 0) or 0)
