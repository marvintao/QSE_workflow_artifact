# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Agent runtime: a thin tool-loop on top of LLMClient.call_with_tools().

Provides the Tool dataclass plus the run_agent() main loop. The runtime
is provider-agnostic.
"""
import json
import time
from dataclasses import dataclass, field
from typing import Callable

from .protocol import LLMClient, ToolCall, ToolResult

# Max length of a single tool output (character count); excess is truncated and `[truncated]` is appended.
_TOOL_OUTPUT_LIMIT = 8192


@dataclass
class Tool:
    """A tool callable by the agent: name + description + JSON-Schema parameters + executor function."""

    name: str
    description: str
    parameters_schema: dict
    run: Callable[[dict], str]

    def to_openai_schema(self) -> dict:
        """Convert to the OpenAI function-calling tools protocol dict (also compatible with Anthropic)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


@dataclass
class AgentRound:
    """Full record of one agent iteration."""

    round_number: int
    thought: str | None
    tool_calls: list[ToolCall]
    tool_results: list[ToolResult]
    duration_ms: int
    token_usage: dict


@dataclass
class AgentOutcome:
    """Final result returned when the agent stops."""

    success: bool
    final_text: str | None = None
    rounds: list[AgentRound] = field(default_factory=list)
    failure_reason: str | None = None
    total_tokens: int = 0


def _truncate(s: str) -> str:
    """Truncate oversized tool output and append `[truncated]` to keep the context budget under control."""
    if len(s) <= _TOOL_OUTPUT_LIMIT:
        return s
    return s[:_TOOL_OUTPUT_LIMIT] + "\n... [truncated]"


def _exec_tool(tool: Tool, args: dict, tc: ToolCall) -> ToolResult:
    """Execute a single tool call; on exception wrap it into ToolResult(is_error=True)."""
    try:
        out = tool.run(args)
    except Exception as e:  # noqa: BLE001 - caught and fed back to the agent
        return ToolResult(
            tool_id=tc.tool_id, tool_name=tc.tool_name,
            output=f"{type(e).__name__}: {e}", is_error=True,
        )
    return ToolResult(
        tool_id=tc.tool_id, tool_name=tc.tool_name,
        output=_truncate(str(out)), is_error=False,
    )


def run_agent(
    *, llm: LLMClient,
    system_prompt: str,
    user_prompt: str,
    tools: dict[str, Tool],
    max_iterations: int,
    max_tool_calls: int,
    max_tokens: int,
    on_round: Callable[[AgentRound], None] | None = None,
) -> AgentOutcome:
    """Main loop: LLM -> tool_calls -> execute -> feed back -> until a final answer or the budget is exhausted.

    on_round: callback fired at the end of each round, used to persist
    agent_round trace records in real time.
    """
    tools_schema = [t.to_openai_schema() for t in tools.values()]
    rounds: list[AgentRound] = []
    total_tokens = 0
    tool_call_count = 0
    # Accumulated message history (OpenAI shape) for multi-round iteration.
    history: list[dict] = [{"role": "user", "content": user_prompt}]

    for i in range(max_iterations):
        t0 = time.monotonic()
        text, tcs, usage = llm.call_with_tools(
            system=system_prompt, user=user_prompt,
            tools=tools_schema, previous_messages=history)
        duration_ms = int((time.monotonic() - t0) * 1000)
        total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        # No tool calls -> final answer.
        if not tcs:
            round_rec = AgentRound(
                round_number=i, thought=text, tool_calls=[],
                tool_results=[], duration_ms=duration_ms, token_usage=usage)
            rounds.append(round_rec)
            if on_round:
                on_round(round_rec)
            if text is None:
                return AgentOutcome(success=False, rounds=rounds,
                    failure_reason="empty_final_text",
                    total_tokens=total_tokens)
            return AgentOutcome(success=True, final_text=text,
                rounds=rounds, total_tokens=total_tokens)

        # Tool calls present -> execute each; if the tool-call budget is exceeded mid-batch, fail.
        tool_results: list[ToolResult] = []
        for tc in tcs:
            tool_call_count += 1
            if tool_call_count > max_tool_calls:
                round_rec = AgentRound(
                    round_number=i, thought=text, tool_calls=tcs,
                    tool_results=tool_results, duration_ms=duration_ms,
                    token_usage=usage)
                rounds.append(round_rec)
                if on_round:
                    on_round(round_rec)
                return AgentOutcome(success=False, rounds=rounds,
                    failure_reason="tool_calls_exhausted",
                    total_tokens=total_tokens)
            tool = tools.get(tc.tool_name)
            if tool is None:
                tool_results.append(ToolResult(
                    tool_id=tc.tool_id, tool_name=tc.tool_name,
                    output=f"unknown tool: {tc.tool_name}", is_error=True))
                continue
            tool_results.append(_exec_tool(tool, tc.arguments, tc))

        round_rec = AgentRound(
            round_number=i, thought=text, tool_calls=tcs,
            tool_results=tool_results, duration_ms=duration_ms,
            token_usage=usage)
        rounds.append(round_rec)
        if on_round:
            on_round(round_rec)

        # Append context (OpenAI message format): assistant tool_calls + each tool result.
        history.append({
            "role": "assistant",
            "content": text or "",
            "tool_calls": [{
                "id": tc.tool_id, "type": "function",
                "function": {"name": tc.tool_name,
                              "arguments": json.dumps(tc.arguments)},
            } for tc in tcs],
        })
        for tr in tool_results:
            history.append({
                "role": "tool",
                "tool_call_id": tr.tool_id,
                "content": tr.output,
            })

        if total_tokens >= max_tokens:
            return AgentOutcome(success=False, rounds=rounds,
                failure_reason="tokens_exhausted",
                total_tokens=total_tokens)

    return AgentOutcome(success=False, rounds=rounds,
        failure_reason="iterations_exhausted",
        total_tokens=total_tokens)
