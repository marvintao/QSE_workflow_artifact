"""Claude Agent SDK client: uses subscription OAuth (no ANTHROPIC_API_KEY required).

The SDK relies on the local `claude` CLI's OAuth credentials. This is
useful for Claude Code Max subscribers who want the backend to call the
Claude API without obtaining a separate API key.

Step 1 coverage: simple call() / call_json() — sufficient for the 6
non-agent stages parse / analyze / blueprint / encode / combine /
global_review.

Step 2 (later): codegen / verify are real agents whose tool loop is
driven by our AgenticRuntime (single-shot LLM call_with_tools + Python
executes the tool + feeds the next round). The SDK's built-in agent
loop is incompatible with that model. Supporting these stages via the
SDK would require rewriting them as "SDK drives the loop + custom MCP
server provides tools", which is a much larger effort. In Step 1
call_with_tools raises NotImplementedError so users misconfiguring
codegen / verify_agent to claude_sdk get a clear error.
"""
import asyncio
import json
import time

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from .protocol import (
    LLMError,
    ToolCall,
    strip_code_fences,
    try_parse_json_tolerant,
)


class ClaudeSDKClient:
    """LLM client backed by claude-agent-sdk (subscription OAuth; no API key required)."""

    def __init__(
        self,
        model: str,
        max_retries: int = 3,
        base_delay_s: float = 1.0,
        max_tokens: int = 1_048_576,
        timeout: float = 90.0,
    ):
        """Initialize the client.

        Args:
            model: Claude model ID (e.g. "claude-opus-4-7" / "claude-sonnet-4-6").
            max_retries: Max retry attempts on failure.
            base_delay_s: Base exponential-backoff seconds.
            max_tokens / timeout: Kept for interface compatibility. The
                SDK does not expose either over OAuth, but they remain
                in the signature so deps.py can mirror the other
                clients during injection.
        """
        self.model = model
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self.max_tokens = max_tokens
        self.timeout = timeout

    @staticmethod
    def _merge_usage(target: dict, src: dict | None) -> None:
        if not src:
            return
        for k in ("input_tokens", "output_tokens",
                  "cache_creation_input_tokens",
                  "cache_read_input_tokens"):
            target[k] += int(src.get(k, 0) or 0)

    # Any of the following signals is treated as a rate limit
    # (subscription OAuth tripped the 5h window):
    # - ResultMessage.api_error_status == 429
    # - ResultMessage.subtype contains "rate_limit" / "limit"
    # - errors text contains rate_limit / 429
    # The raised LLMError message is prefixed with "RATE_LIMIT:" so
    # batch scripts can detect and pause.
    _RATE_LIMIT_MARKER = "RATE_LIMIT:"

    @classmethod
    def is_rate_limit_error(cls, message: str) -> bool:
        """Used by batch scripts to check whether an LLMError is a rate-limit error."""
        return cls._RATE_LIMIT_MARKER in (message or "")

    async def _async_call(self, system: str, user: str) -> tuple[str, dict]:
        """Drive the SDK `query` asynchronously with max_turns=1 (pure-text response, no tool loop)."""
        options = ClaudeAgentOptions(
            system_prompt=system,
            model=self.model,
            max_turns=1,
            # bypassPermissions: tell the SDK not to prompt for tool approval (we don't allow any tools here).
            permission_mode="bypassPermissions",
        )
        text_parts: list[str] = []
        usage = {
            "input_tokens": 0, "output_tokens": 0,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
        }
        async for msg in query(prompt=user, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                self._merge_usage(usage, msg.usage)
                # AssistantMessage.error reports problems directly (the
                # SDK surfaces rate_limit / authentication_failed /
                # billing_error / server_error etc. here). The previous
                # simple-call path didn't handle this field explicitly,
                # so failures only showed up in long traces. Fail-fast here.
                if msg.error:
                    # rate_limit: explicitly reported by the SDK.
                    # unknown: the SDK reports OAuth-window rate
                    # limiting as "unknown" (empirically: multiple
                    # round-2 reqs running 1.5-2h all return "unknown",
                    # a clear pattern).
                    is_rl = msg.error in ("rate_limit", "unknown")
                    prefix = (self._RATE_LIMIT_MARKER + " "
                              if is_rl else "")
                    raise LLMError(
                        f"{prefix}SDK AssistantMessage error: {msg.error}"
                    )
            elif isinstance(msg, ResultMessage):
                if msg.is_error:
                    # Roll every diagnostic field into the message:
                    # previously we only inspected errors/subtype and
                    # missed api_error_status, which made rate-limit
                    # (429) responses surface misleadingly as
                    # "ResultMessage error: success".
                    api_status = msg.api_error_status
                    subtype = msg.subtype or ""
                    errs = "; ".join(msg.errors or [])
                    stop_reason = msg.stop_reason or ""
                    # weird_silent_error: empirical signal — when
                    # Claude Code Max subscription OAuth hits the 5h
                    # window, the SDK does not expose the 429 and
                    # instead returns the odd combination
                    # `is_error=True + subtype="success" + errors=[] +
                    # api_status=None` (in the last batch 386/400
                    # failures took this exact shape).
                    weird_silent_error = (
                        subtype.lower() == "success"
                        and not msg.errors
                        and api_status is None
                    )
                    is_rl = (
                        api_status == 429
                        or "rate_limit" in subtype.lower()
                        or "rate_limit" in errs.lower()
                        or "rate limit" in errs.lower()
                        or weird_silent_error
                    )
                    prefix = self._RATE_LIMIT_MARKER + " " if is_rl else ""
                    raise LLMError(
                        f"{prefix}Claude SDK ResultMessage error: "
                        f"subtype={subtype!r} api_status={api_status} "
                        f"stop_reason={stop_reason!r} "
                        f"errors=[{errs}]"
                    )
                self._merge_usage(usage, msg.usage)
        return "".join(text_parts).strip(), usage

    def call(
        self, *, system: str, user: str, cache_system: bool = False
    ) -> tuple[str, dict]:
        """Synchronous entry point: SDK simple query with exponential-backoff retry.

        cache_system is kept for interface compatibility; the SDK
        decides caching automatically and we do not control it
        explicitly.
        """
        _ = cache_system
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return asyncio.run(self._async_call(system, user))
            except Exception as e:  # noqa: BLE001 - retry envelope
                last_exc = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay_s * (2 ** attempt))
        raise LLMError(
            f"Claude SDK call failed after {self.max_retries} attempts: "
            f"{last_exc}"
        ) from last_exc

    def call_json(
        self, *, system: str, user: str, cache_system: bool = False
    ) -> tuple[dict, dict]:
        """Synchronous entry point: SDK call, then strip markdown fences and tolerant-parse JSON."""
        text, usage = self.call(
            system=system, user=user, cache_system=cache_system
        )
        cleaned = strip_code_fences(text)
        try:
            return try_parse_json_tolerant(cleaned), usage
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Claude SDK returned non-JSON: {text[:20000]}"
            ) from e

    def call_with_tools(
        self, *, system: str, user: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> tuple[str | None, list[ToolCall], dict]:
        """Not supported in Step 1: the codegen / verify agent loops
        are driven by AgenticRuntime and cannot be fed straight into
        the SDK's built-in agent loop. Support arrives only after Step
        2 rewrites them as SDK + MCP-server agents.

        Currently raises NotImplementedError so that users misconfiguring
        codegen_agent / verify_agent to claude_sdk:... get a clear
        error rather than a silent failure.
        """
        _ = system, user, tools, previous_messages  # mark parameters as consumed
        raise NotImplementedError(
            "ClaudeSDKClient.call_with_tools is not implemented in Step 1. "
            "Configure CODEGEN_AGENT / VERIFY_AGENT to use a different "
            "provider (kimi / zhipu / siliconflow / claude with API key). "
            "Step 2 will rewrite codegen / verify as SDK-native MCP-server "
            "agents to support OAuth-only tool calling."
        )
