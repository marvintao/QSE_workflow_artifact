"""Zhipu (BigModel) client: OpenAI-compatible API targeting the GLM family.

API docs: https://open.bigmodel.cn/dev/api
Default base_url: https://open.bigmodel.cn/api/paas/v4
Typical models: glm-4-plus / glm-4 / glm-4-flash / glm-4.5 / glm-4.5-air
The GLM family supports OpenAI-style function calling (the `tools` field).
"""

import json
import time

from openai import OpenAI

from .protocol import (
    LLMError,
    ToolCall,
    strip_code_fences,
    try_parse_json_tolerant,
)


# The Zhipu GLM family enforces a hard per-response max_tokens cap
# (typically 8192, sometimes 4096); exceeding it makes the server return
# 400 with code 1210. The client layer hard-clamps the global max_tokens
# (default 1_048_576, intended for Claude/SF) to the GLM-safe value.
# Users needing more headroom should switch zhipu_model to a higher-cap
# version in config.
_ZHIPU_MAX_TOKENS_CAP = 8192


class ZhipuClient:
    """LLM client implementation backed by Zhipu BigModel (OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_retries: int = 3,
        base_delay_s: float = 1.0,
        max_tokens: int = 1_048_576,
        timeout: float = 90.0,
    ):
        """Initialize the client.

        Args:
            api_key: Zhipu BigModel API key.
            base_url: API base URL (defaults to https://open.bigmodel.cn/api/paas/v4).
            model: Fully qualified model name (e.g. glm-4-plus / glm-4.5).
            max_retries: Max retry attempts.
            base_delay_s: Base wait in seconds for exponential backoff.
            max_tokens: Max tokens per response.
            timeout: Per-request timeout in seconds.
        """
        self._client = OpenAI(api_key=api_key, base_url=base_url,
                              timeout=timeout)
        self.model = model
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self.max_tokens = max_tokens

    def call(
        self, *, system: str, user: str, cache_system: bool = False
    ) -> tuple[str, dict]:
        """Send a single chat request to Zhipu, with exponential-backoff retry on failure.

        Args:
            system: System prompt.
            user: User message content.
            cache_system: Reserved parameter. Zhipu does not currently
                support Anthropic-style ephemeral prompt cache; the
                flag is silently ignored.
        Returns:
            (response text, token-usage dict).
        """
        # Zhipu BigModel follows the OpenAI-compatible protocol; no Anthropic-style ephemeral cache.
        _ = cache_system

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    max_tokens=min(self.max_tokens, _ZHIPU_MAX_TOKENS_CAP),
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                text = resp.choices[0].message.content or ""
                # Map OpenAI field names into the platform's unified usage schema; cache fields fill 0.
                usage = {
                    "input_tokens": resp.usage.prompt_tokens,
                    "output_tokens": resp.usage.completion_tokens,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                }
                return text, usage
            except Exception as e:  # noqa: BLE001 - retry envelope
                last_exc = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay_s * (2 ** attempt))
        raise LLMError(
            f"Zhipu call failed after {self.max_retries} attempts: {last_exc}"
        ) from last_exc

    def call_json(
        self, *, system: str, user: str, cache_system: bool = False
    ) -> tuple[dict, dict]:
        """Call Zhipu and parse the response as a JSON dict."""
        text, usage = self.call(
            system=system, user=user, cache_system=cache_system
        )
        cleaned = strip_code_fences(text)
        try:
            return try_parse_json_tolerant(cleaned), usage
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Zhipu returned non-JSON: {text[:20000]}") from e

    def call_with_tools(
        self, *, system: str, user: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> tuple[str | None, list[ToolCall], dict]:
        """Single-round tool-use call via the OpenAI-compatible protocol.

        previous_messages is the accumulated message history for the
        session, used for multi-round iteration; when None, `user` is
        used as the first-round user input.
        """
        msgs: list[dict] = [{"role": "system", "content": system}]
        if previous_messages:
            msgs.extend(previous_messages)
        else:
            msgs.append({"role": "user", "content": user})

        # Zhipu GLM tool calling requires explicit tool_choice=auto.
        # Without it some models/gateways simply close the connection
        # ("Server disconnected without sending a response"). The
        # OpenAI SDK omits tool_choice by default — Zhipu does not
        # accept the implicit form.
        kwargs: dict = {
            "model": self.model,
            "max_tokens": min(self.max_tokens, _ZHIPU_MAX_TOKENS_CAP),
            "messages": msgs,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        # Reasoning models such as GLM-4.5 / 4.7 / 5.x have thinking
        # enabled by default and emit reasoning_content. **In multi-
        # round tool calling reasoning_content must be echoed back**
        # or the gateway disconnects (same issue as Kimi k2-thinking).
        # The tool loop is inherently multi-round, and echoing
        # reasoning_content is fiddly, so disable thinking explicitly
        # here to trade for stable tool-calling behavior. The flag is
        # passed through via the OpenAI SDK's extra_body field.
        extra_body = {"thinking": {"type": "disabled"}}
        resp = self._client.chat.completions.create(
            **kwargs, extra_body=extra_body)
        choice = resp.choices[0].message
        usage = {
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        tcs = choice.tool_calls or []
        tool_calls = [ToolCall(
            tool_id=tc.id,
            tool_name=tc.function.name,
            arguments=json.loads(tc.function.arguments or "{}"),
        ) for tc in tcs]
        return (choice.content or None), tool_calls, usage
