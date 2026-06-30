"""SiliconFlow client: talks to SiliconFlow via its OpenAI-compatible API, with retried synchronous calls."""

import json
import time

from openai import OpenAI

from .protocol import (
    LLMError,
    ToolCall,
    strip_code_fences,
    try_parse_json_tolerant,
)


class SiliconFlowClient:
    """LLM client implementation backed by SiliconFlow (OpenAI-compatible API).

    A single SiliconFlow endpoint fronts multiple underlying models
    (DeepSeek / Qwen / GLM, etc.); the model name is supplied via the
    `model` constructor argument.
    """

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
            api_key: SiliconFlow API key.
            base_url: API base URL (e.g. https://api.siliconflow.cn/v1).
            model: Fully qualified model name (e.g. deepseek-ai/DeepSeek-V4-Flash).
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
        """Send a single chat request to SiliconFlow, with exponential-backoff retry on failure.

        Args:
            system: System prompt.
            user: User message content.
            cache_system: Reserved parameter. SiliconFlow does not
                currently support Anthropic-style ephemeral prompt
                cache; the flag is silently ignored.
        Returns:
            (response text, token-usage dict).
        """
        # SiliconFlow follows the OpenAI-compatible protocol; no Anthropic-style ephemeral cache.
        _ = cache_system

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
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
            f"SiliconFlow call failed after {self.max_retries} attempts: "
            f"{last_exc}"
        ) from last_exc

    def call_json(
        self, *, system: str, user: str, cache_system: bool = False
    ) -> tuple[dict, dict]:
        """Call SiliconFlow and parse the response as a JSON dict."""
        text, usage = self.call(
            system=system, user=user, cache_system=cache_system
        )
        cleaned = strip_code_fences(text)
        try:
            return try_parse_json_tolerant(cleaned), usage
        except json.JSONDecodeError as e:
            raise LLMError(
                f"SiliconFlow returned non-JSON: {text[:20000]}") from e

    def call_with_tools(
        self, *, system: str, user: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> tuple[str | None, list[ToolCall], dict]:
        """Single-round tool-use call via the OpenAI-compatible protocol.

        previous_messages is the accumulated message history of the
        current session, used for multi-round iteration; when None,
        `user` is used as the first-round user input.
        """
        msgs: list[dict] = [{"role": "system", "content": system}]
        if previous_messages:
            msgs.extend(previous_messages)
        else:
            msgs.append({"role": "user", "content": user})

        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=msgs,
            tools=tools if tools else None,
        )
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
