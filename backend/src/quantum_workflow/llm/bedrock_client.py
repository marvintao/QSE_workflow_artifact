"""AWS Bedrock client: talks to models on Bedrock (Llama / Claude /
Mistral, etc.) via the Converse API, with retried synchronous calls.

The Bedrock Converse API is a model-agnostic unified interface
supporting every Llama 3.x / 4.x, Claude, Mistral, and Cohere model;
its response shape is uniform across models.

Authentication: relies on the boto3 default credentials chain
(env -> ~/.aws/credentials -> IAM role); no explicit key is passed
through this class.
"""

import json
import time

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionError as BotoConnectionError,
    ReadTimeoutError,
)

from .protocol import (
    LLMError,
    ToolCall,
    strip_code_fences,
    try_parse_json_tolerant,
)


# Consistent with the other clients: prefix the rate-limit error
# message with a marker so batch scripts can detect and pause on it.
_RATE_LIMIT_MARKER = "RATE_LIMIT:"


class BedrockClient:
    """LLM client implementation backed by the AWS Bedrock Converse API.

    Converse is a model-agnostic unified interface with a uniform
    messages format and toolConfig format. It supports all Llama 3.x /
    4.x, Claude, Mistral, and similar Bedrock models, and its response
    fields are uniform too.

    AWS credentials use the boto3 default chain (env vars /
    ~/.aws/credentials / IAM role); no key is passed through this class.
    """

    def __init__(
        self,
        region: str,
        model: str,
        max_retries: int = 3,
        base_delay_s: float = 1.0,
        max_tokens: int = 4096,
        timeout: float = 90.0,
    ):
        """Initialize the client.

        Args:
            region: AWS region (e.g. us-east-1).
            model: Bedrock model ID (e.g. meta.llama4-maverick-17b-instruct-v1:0).
            max_retries: Max business-layer retries for transient errors.
            base_delay_s: Base exponential-backoff seconds.
            max_tokens: Cap for Converse `inferenceConfig.maxTokens`.
            timeout: Per-request boto3 client read timeout in seconds.
        """
        cfg = BotoConfig(
            region_name=region,
            read_timeout=timeout,
            retries={"max_attempts": 0, "mode": "standard"},   # business layer handles its own retry
        )
        self._client = boto3.client("bedrock-runtime", config=cfg)
        self.model = model
        self.region = region
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self.max_tokens = max_tokens

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        """Identify Bedrock throttling / rate-limit errors.

        ClientError codes such as ThrottlingException /
        TooManyRequestsException / ServiceUnavailableException / 429.
        """
        if isinstance(exc, ClientError):
            code = exc.response.get("Error", {}).get("Code", "")
            return code in {"ThrottlingException", "TooManyRequestsException",
                            "ServiceUnavailableException", "Throttling"}
        return False

    def _wrap_rate_limit(self, exc: Exception) -> LLMError:
        prefix = self._RATE_LIMIT_MARKER + " " if self._is_rate_limit(exc) else ""
        return LLMError(
            f"{prefix}Bedrock Converse failed after {self.max_retries} "
            f"attempts: {type(exc).__name__}: {exc}"
        )

    _RATE_LIMIT_MARKER = _RATE_LIMIT_MARKER

    def call(
        self, *, system: str, user: str, cache_system: bool = False
    ) -> tuple[str, dict]:
        """Send a single chat request to Bedrock Converse, with exponential-backoff retry on failure.

        Args:
            system: System prompt.
            user: User message content.
            cache_system: Reserved parameter. Bedrock Converse does not
                support Anthropic-style ephemeral cache directly (some
                Anthropic models expose promptCachingConfig, but Llama
                does not); silently ignored.
        Returns:
            (response text, token-usage dict).
        """
        _ = cache_system   # No ephemeral cache on the Llama path; ignored.

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.converse(
                    modelId=self.model,
                    messages=[{"role": "user",
                                "content": [{"text": user}]}],
                    system=[{"text": system}] if system else None,
                    inferenceConfig={
                        "maxTokens": self.max_tokens,
                    },
                )
                text = self._extract_text(resp)
                usage = self._extract_usage(resp)
                return text, usage
            except (BotoConnectionError, ReadTimeoutError, BotoCoreError,
                    ClientError) as e:
                last_exc = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay_s * (2 ** attempt))
        raise self._wrap_rate_limit(last_exc) from last_exc

    def call_json(
        self, *, system: str, user: str, cache_system: bool = False
    ) -> tuple[dict, dict]:
        """Call Bedrock and parse the response as a JSON dict."""
        text, usage = self.call(
            system=system, user=user, cache_system=cache_system
        )
        cleaned = strip_code_fences(text)
        try:
            return try_parse_json_tolerant(cleaned), usage
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Bedrock returned non-JSON: {text[:20000]}") from e

    def call_with_tools(
        self, *, system: str, user: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> tuple[str | None, list[ToolCall], dict]:
        """Single-round tool-use call using the Bedrock Converse toolConfig protocol.

        Args:
            tools: OpenAI-style tool schemas, converted to Converse
                `toolSpec` format
                ([{toolSpec: {name, description, inputSchema: {json: {...}}}}]).
            previous_messages: AgenticRuntime-accumulated OpenAI-shape
                messages (content=string, assistant.tool_calls=[...],
                tool message role=tool); this method normalizes them
                into Converse format (content = list of
                {text|toolUse|toolResult} blocks; tool results become a
                role=user message with toolResult blocks). When None,
                `user` is used as the first round.
        """
        if previous_messages:
            msgs = self._oai_to_converse_messages(previous_messages)
        else:
            msgs = [{"role": "user", "content": [{"text": user}]}]

        # OpenAI tool schema {name, description, parameters} -> Converse toolSpec.
        tool_config = None
        if tools:
            converse_tools = []
            for t in tools:
                fn = t.get("function") or t
                converse_tools.append({
                    "toolSpec": {
                        "name": fn["name"],
                        "description": fn.get("description", ""),
                        "inputSchema": {"json": fn.get("parameters")
                                         or {"type": "object", "properties": {}}},
                    }
                })
            tool_config = {"tools": converse_tools}

        try:
            kwargs = dict(
                modelId=self.model, messages=msgs,
                inferenceConfig={"maxTokens": self.max_tokens},
            )
            if system:
                kwargs["system"] = [{"text": system}]
            if tool_config:
                kwargs["toolConfig"] = tool_config
            resp = self._client.converse(**kwargs)
        except (BotoConnectionError, ReadTimeoutError, BotoCoreError,
                ClientError) as e:
            raise self._wrap_rate_limit(e) from e

        text = self._extract_text(resp)
        usage = self._extract_usage(resp)
        tool_calls = self._extract_tool_calls(resp)
        return (text or None), tool_calls, usage

    # ---------- helpers ----------

    @staticmethod
    def _extract_text(resp: dict) -> str:
        """Extract text content from a Converse response (may coexist with toolUse blocks)."""
        out = resp.get("output", {}).get("message", {}).get("content", [])
        return "".join(b["text"] for b in out if "text" in b).strip()

    @staticmethod
    def _extract_usage(resp: dict) -> dict:
        """Map Converse usage into the platform's unified 4-field schema.

        Cache fields are hardcoded to 0 since the Bedrock Llama path has
        no ephemeral cache.
        """
        u = resp.get("usage", {}) or {}
        return {
            "input_tokens": int(u.get("inputTokens", 0)),
            "output_tokens": int(u.get("outputTokens", 0)),
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }

    @staticmethod
    def _oai_to_converse_messages(history: list[dict]) -> list[dict]:
        """Translate AgenticRuntime-accumulated OpenAI-shape history into Bedrock Converse format.

        Input (OpenAI):
          {"role": "user", "content": "string"}
          {"role": "assistant", "content": "string",
           "tool_calls": [{"id": X, "type": "function",
                            "function": {"name": Y, "arguments": <JSON str>}}, ...]}
          {"role": "tool", "tool_call_id": X, "content": "string"}

        Output (Converse):
          {"role": "user", "content": [{"text": "string"}]}
          {"role": "assistant", "content": [
              {"text": "string"},     # optional, only when content is non-empty
              {"toolUse": {"toolUseId": X, "name": Y, "input": <parsed dict>}},
          ]}
          {"role": "user", "content": [
              {"toolResult": {"toolUseId": X1, "content": [{"text": "..."}]}},
              {"toolResult": {"toolUseId": X2, "content": [{"text": "..."}]}},
              ...     # multiple toolResult blocks merged into one user
                      # message, paired strictly 1:1 with the prior
                      # assistant message's N toolUse blocks (required
                      # by Bedrock).
          ]}

        Bedrock strict requirement: an assistant message with N
        toolUse blocks must be followed by a single user message
        containing N toolResult blocks in the same content list (not N
        separate user messages). OpenAI format uses N standalone tool
        messages, so this function merges adjacent tool messages into a
        single user message.
        """
        out: list[dict] = []
        pending_tool_results: list[dict] = []   # toolResult blocks waiting to be merged

        def flush_tool_results():
            """Merge accumulated toolResult blocks into a single user message."""
            if pending_tool_results:
                out.append({"role": "user",
                             "content": list(pending_tool_results)})
                pending_tool_results.clear()

        for m in history:
            role = m.get("role")
            content = m.get("content")
            if role == "user":
                flush_tool_results()
                text = content if isinstance(content, str) else str(content or "")
                out.append({"role": "user",
                             "content": [{"text": text}] if text else []})
            elif role == "assistant":
                flush_tool_results()
                blocks: list[dict] = []
                text = content if isinstance(content, str) else ""
                if text:
                    blocks.append({"text": text})
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function", {})
                    args_raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(args_raw) if isinstance(
                            args_raw, str) else (args_raw or {})
                    except (ValueError, TypeError):
                        args = {}
                    blocks.append({"toolUse": {
                        "toolUseId": tc.get("id") or fn.get("name", ""),
                        "name": fn.get("name", ""),
                        "input": args,
                    }})
                if blocks:
                    out.append({"role": "assistant", "content": blocks})
            elif role == "tool":
                # OpenAI tool result -> buffer until the next flush (merged into one user message).
                text = content if isinstance(content, str) else str(content or "")
                pending_tool_results.append({
                    "toolResult": {
                        "toolUseId": m.get("tool_call_id", ""),
                        "content": [{"text": text}],
                    }
                })
            # System messages are not handled here (Converse uses the top-level `system` parameter).
        flush_tool_results()   # Flush any trailing tool results at end-of-history.
        return out

    @staticmethod
    def _extract_tool_calls(resp: dict) -> list[ToolCall]:
        out = resp.get("output", {}).get("message", {}).get("content", [])
        calls = []
        for block in out:
            if "toolUse" in block:
                tu = block["toolUse"]
                calls.append(ToolCall(
                    tool_id=tu.get("toolUseId", ""),
                    tool_name=tu.get("name", ""),
                    arguments=tu.get("input") or {},
                ))
        return calls
