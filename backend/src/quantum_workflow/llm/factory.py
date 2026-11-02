# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""LLM factory: select and instantiate the LLM client matching the configuration
(Claude / Kimi / SiliconFlow / Zhipu / AWS Bedrock)."""

from quantum_workflow.config import Settings

from .bedrock_client import BedrockClient
from .claude_client import ClaudeClient
from .claude_sdk_client import ClaudeSDKClient
from .kimi_client import KimiClient
from .protocol import LLMClient
from .siliconflow_client import SiliconFlowClient
from .zhipu_client import ZhipuClient


def build_llm_client(settings: Settings) -> LLMClient:
    """Build and return the LLMClient instance matching the configuration.

    Raises ValueError immediately when the selected provider is missing
    a required API key, so the failure surfaces at startup instead of
    mid-pipeline.
    """
    provider = settings.llm_provider
    if provider == "claude":
        if not settings.anthropic_api_key:
            raise ValueError(
                "LLM_PROVIDER=claude requires ANTHROPIC_API_KEY"
            )
        return ClaudeClient(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    if provider == "kimi":
        if not settings.kimi_api_key:
            raise ValueError(
                "LLM_PROVIDER=kimi requires KIMI_API_KEY"
            )
        return KimiClient(
            api_key=settings.kimi_api_key,
            base_url=settings.kimi_base_url,
            model=settings.kimi_model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    if provider == "siliconflow":
        if not settings.siliconflow_api_key:
            raise ValueError(
                "LLM_PROVIDER=siliconflow requires SILICONFLOW_API_KEY"
            )
        return SiliconFlowClient(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url,
            model=settings.siliconflow_model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    if provider == "zhipu":
        if not settings.zhipu_api_key:
            raise ValueError(
                "LLM_PROVIDER=zhipu requires ZHIPU_API_KEY"
            )
        return ZhipuClient(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url,
            model=settings.zhipu_model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    if provider == "claude_sdk":
        # claude_sdk uses subscription OAuth (local claude CLI
        # credentials) and needs no API key. codegen / verify and other
        # real agents raise NotImplementedError when call_with_tools is
        # invoked — users must point those 2 stages at a different
        # provider.
        return ClaudeSDKClient(
            model=settings.claude_sdk_model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    if provider == "bedrock":
        # AWS Bedrock uses the boto3 default credentials chain (env /
        # profile / IAM role); there is no API-key field to validate.
        # `model` is the Bedrock model ID (e.g.
        # meta.llama4-maverick-17b-instruct-v1:0).
        return BedrockClient(
            region=settings.bedrock_region,
            model=settings.bedrock_model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    raise ValueError(f"unknown LLM_PROVIDER: {provider!r}")


# Known provider set (used by build_llm_for_stage for override parsing/validation).
_KNOWN_PROVIDERS = {"claude", "claude_sdk", "kimi", "siliconflow", "zhipu",
                     "bedrock"}


def build_llm_for_stage(settings: Settings, stage_name: str) -> LLMClient:
    """Build the LLM client for a given stage: prefer the `<stage>_agent` setting; fall back to the global config.

    Config format: `<provider>:<model>`, e.g. `kimi:moonshot-v1-32k`.
    Empty string -> fall back to `build_llm_client(settings)` directly.
    Malformed value or unknown provider -> raise ValueError immediately
    (fail fast).
    """
    attr = f"{stage_name}_agent"
    override = getattr(settings, attr, "")
    if not override:
        return build_llm_client(settings)

    # Parse "<provider>:<model>"
    if ":" not in override:
        raise ValueError(
            f"{attr.upper()} must be '<provider>:<model>', got {override!r}"
        )
    provider, _, model = override.partition(":")
    provider = provider.strip().lower()
    model = model.strip()
    if not provider or not model:
        raise ValueError(
            f"{attr.upper()} has empty provider or model: {override!r}"
        )
    if provider not in _KNOWN_PROVIDERS:
        raise ValueError(
            f"{attr.upper()} unknown provider {provider!r}; "
            f"expected one of {sorted(_KNOWN_PROVIDERS)}"
        )

    # Build the client for the requested provider, reusing the global retry/timeout.
    if provider == "claude":
        if not settings.anthropic_api_key:
            raise ValueError(
                f"{attr.upper()}=claude:... requires ANTHROPIC_API_KEY"
            )
        return ClaudeClient(
            api_key=settings.anthropic_api_key, model=model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    if provider == "kimi":
        if not settings.kimi_api_key:
            raise ValueError(
                f"{attr.upper()}=kimi:... requires KIMI_API_KEY"
            )
        return KimiClient(
            api_key=settings.kimi_api_key,
            base_url=settings.kimi_base_url,
            model=model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    if provider == "siliconflow":
        if not settings.siliconflow_api_key:
            raise ValueError(
                f"{attr.upper()}=siliconflow:... requires SILICONFLOW_API_KEY"
            )
        return SiliconFlowClient(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url,
            model=model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    if provider == "claude_sdk":
        # claude_sdk:<model> — subscription OAuth (local claude CLI
        # credentials), no API-key validation. codegen / verify agent
        # loops raise NotImplementedError when they hit call_with_tools.
        return ClaudeSDKClient(
            model=model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    if provider == "bedrock":
        # bedrock:<model_id> — boto3 default credentials chain. `model`
        # is the literal Bedrock model ID (e.g.
        # meta.llama4-maverick-17b-instruct-v1:0 or
        # anthropic.claude-3-5-sonnet-20241022-v2:0).
        return BedrockClient(
            region=settings.bedrock_region,
            model=model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout_s,
        )
    # zhipu
    if not settings.zhipu_api_key:
        raise ValueError(
            f"{attr.upper()}=zhipu:... requires ZHIPU_API_KEY"
        )
    return ZhipuClient(
        api_key=settings.zhipu_api_key,
        base_url=settings.zhipu_base_url,
        model=model,
        max_retries=settings.llm_max_retries,
        timeout=settings.llm_timeout_s,
    )
