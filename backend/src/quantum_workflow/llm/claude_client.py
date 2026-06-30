"""Claude client: wraps the Anthropic SDK, exposing a synchronous call interface with exponential-backoff retry."""

import json
import time

from anthropic import Anthropic

from .protocol import (
    LLMError,
    ToolCall,
    strip_code_fences,
    try_parse_json_tolerant,
)


class ClaudeClient:
    """LLM client implementation backed by the Anthropic Messages API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_retries: int = 3,
        base_delay_s: float = 1.0,
        max_tokens: int = 1_048_576,
        timeout: float = 90.0,
    ):
        """Initialize the client.

        Args:
            api_key: Anthropic API key.
            model: Model name (e.g. claude-3-5-sonnet-20241022).
            max_retries: Maximum number of retries.
            base_delay_s: Base wait in seconds for exponential backoff.
            max_tokens: Max tokens per response.
            timeout: Per-request timeout in seconds.
        """
        self._client = Anthropic(api_key=api_key, timeout=timeout)
        self.model = model
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self.max_tokens = max_tokens

    def call(
        self, *, system: str, user: str, cache_system: bool = False
    ) -> tuple[str, dict]:
        """Send a single chat request to Claude with exponential-backoff retry on failure.

        Args:
            system: System prompt.
            user: User message content.
            cache_system: When True, enable ephemeral prompt cache on the system prompt.
        Returns:
            (response text, token-usage dict).
        """
        # When caching is enabled, wrap the system prompt as a block list with cache_control; otherwise pass a plain string.
        sys_param = (
            [{"type": "text", "text": system,
              "cache_control": {"type": "ephemeral"}}]
            if cache_system else system
        )

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=sys_param,
                    messages=[{"role": "user", "content": user}],
                )
                text = "".join(
                    b.text for b in resp.content if hasattr(b, "text")
                )
                # Compatibility with older SDKs: cache-related fields may not exist; default to 0 when missing.
                usage = {
                    "input_tokens": resp.usage.input_tokens,
                    "output_tokens": resp.usage.output_tokens,
                    "cache_creation_input_tokens":
                        getattr(resp.usage, "cache_creation_input_tokens", 0),
                    "cache_read_input_tokens":
                        getattr(resp.usage, "cache_read_input_tokens", 0),
                }
                return text, usage
            except Exception as e:  # noqa: BLE001 - retry envelope
                last_exc = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay_s * (2 ** attempt))
        raise LLMError(
            f"Claude call failed after {self.max_retries} attempts: {last_exc}"
        ) from last_exc

    def call_json(
        self, *, system: str, user: str, cache_system: bool = False
    ) -> tuple[dict, dict]:
        """Call Claude and parse the response as a JSON dict.

        Built on call(): strips code fences and deserializes JSON automatically.
        Returns:
            (parsed dict, token-usage dict).
        """
        text, usage = self.call(
            system=system, user=user, cache_system=cache_system
        )
        cleaned = strip_code_fences(text)
        try:
            return try_parse_json_tolerant(cleaned), usage
        except json.JSONDecodeError as e:
            raise LLMError(f"Claude returned non-JSON: {text[:20000]}") from e

    def call_with_tools(
        self, *, system: str, user: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> tuple[str | None, list[ToolCall], dict]:
        """Single-round tool-use call; translates OpenAI-shape tools into Anthropic format.

        previous_messages comes in OpenAI shape and is converted to
        Anthropic content blocks internally.
        """
        # OpenAI tools schema -> Anthropic tools schema.
        anthropic_tools = []
        for t in tools:
            fn = t.get("function", t)
            anthropic_tools.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object"}),
            })

        anthropic_msgs: list[dict] = []
        if previous_messages:
            for m in previous_messages:
                anthropic_msgs.append(self._convert_msg_to_anthropic(m))
        else:
            anthropic_msgs.append({"role": "user", "content": user})

        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": anthropic_msgs,
        }
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
        resp = self._client.messages.create(**kwargs)

        final_text: str | None = None
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                final_text = getattr(block, "text", None)
            elif btype == "tool_use":
                tool_calls.append(ToolCall(
                    tool_id=getattr(block, "id", ""),
                    tool_name=getattr(block, "name", ""),
                    arguments=getattr(block, "input", {}) or {},
                ))
        usage = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "cache_creation_input_tokens":
                getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
            "cache_read_input_tokens":
                getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
        }
        return final_text, tool_calls, usage

    def _convert_msg_to_anthropic(self, msg: dict) -> dict:
        """Translate an OpenAI-shape message into Anthropic content-block format.

        - role=user / assistant plain text: kept as-is.
        - role=tool (OpenAI tool result) -> Anthropic user role + tool_result block.
        - role=assistant with tool_calls -> assistant tool_use blocks.
        """
        role = msg.get("role")
        if role == "tool":
            return {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg["tool_call_id"],
                    "content": msg.get("content", ""),
                }],
            }
        if role == "assistant" and msg.get("tool_calls"):
            blocks: list[dict] = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg["tool_calls"]:
                args = tc["function"]["arguments"]
                if isinstance(args, str):
                    args = json.loads(args) if args else {}
                blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": args,
                })
            return {"role": "assistant", "content": blocks}
        return {"role": role, "content": msg.get("content", "")}
