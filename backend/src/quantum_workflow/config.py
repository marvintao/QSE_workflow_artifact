"""Global configuration module.

Loads settings from a non-hidden `config` file via pydantic-settings.
Supports Claude, Kimi, SiliconFlow, and Zhipu LLM providers, plus
sandbox and pipeline parameters.
"""
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings for the quantum workflow platform.

    Every field can be overridden via the `config` file.

    Groups:
    - LLM provider selection: llm_provider picks Claude / Kimi / SiliconFlow / Zhipu.
    - Storage paths: trace_db_path, assets_dir.
    - Sandbox limits: max qubit count, timeout, memory cap.
    - Pipeline parameters: per-stage timeouts, LLM retry count and request timeout.
    """

    model_config = SettingsConfigDict(env_file="config", extra="ignore")

    # Provider selection
    llm_provider: Literal[
        "claude", "claude_sdk", "kimi", "siliconflow", "zhipu"
    ] = "claude"

    # Claude API key path (required if llm_provider=claude)
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-7"

    # Claude Agent SDK / subscription OAuth path (no ANTHROPIC_API_KEY needed,
    # uses local `claude` CLI credentials). codegen / verify (the two real
    # agents) currently cannot run via the SDK (call_with_tools raises
    # NotImplementedError); the other 6 stages can. Configure per-stage as
    # `<stage>_agent=claude_sdk:claude-opus-4-7`.
    claude_sdk_model: str = "claude-opus-4-7"

    # Kimi / Moonshot (required if llm_provider=kimi)
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-32k"

    # SiliconFlow (required if llm_provider=siliconflow, or when frontend
    # passes a model override).
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model: str = "deepseek-ai/DeepSeek-V4-Flash"

    # Zhipu / BigModel (required if llm_provider=zhipu)
    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_model: str = "glm-4-plus"

    # AWS Bedrock (required if llm_provider=bedrock or *_AGENT=bedrock:...).
    # Uses the boto3 default credentials chain: supports
    # AWS_BEARER_TOKEN_BEDROCK (Bedrock API Key, 2024 feature) /
    # AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY / ~/.aws/credentials / IAM
    # role. This class does not hold a key.
    # Note: Llama 4 requires an inference profile ID (`us.` prefix); the
    # raw model ID does not work — in practice a raw ID raises
    # ValidationException ("on-demand throughput isn't supported, use
    # inference profile ID instead").
    bedrock_region: str = "us-east-1"
    bedrock_model: str = "us.meta.llama4-maverick-17b-instruct-v1:0"

    # Storage
    trace_db_path: str = "./traces.db"
    assets_dir: str = "./assets/store"

    # Sandbox
    sandbox_max_qubits: int = 24
    # sandbox_timeout_s bumped to 180: a 24-qubit QAOA + COBYLA optimization
    # run typically takes 2-3 minutes, and 60s frequently SIGXCPUs. 180s
    # gives codegen-produced code a reasonable budget.
    sandbox_timeout_s: int = 180
    sandbox_memory_mb: int = 2048

    # Pipeline
    stage_timeout_s: int = 60
    # Outer retry default lowered to 1 — the OpenAI SDK already retries
    # internally, so stacking our outer retry on top causes ~9-minute idle
    # waits during SiliconFlow network jitter (2 x 3 x 90s). 1 disables
    # outer retry entirely, relying solely on the SDK; raise it explicitly
    # in config if outer retry is really wanted.
    llm_max_retries: int = 1
    llm_timeout_s: int = 90

    # Per-stage agent override: format "<provider>:<model>"; empty falls
    # back to the global setting.
    parse_agent: str = ""
    analyze_agent: str = ""
    blueprint_agent: str = ""
    encode_agent: str = ""
    codegen_agent: str = ""
    combine_agent: str = ""
    verify_agent: str = ""
    # global_review reviews the codegen output against the original
    # requirements between codegen and execute. When empty it falls back to
    # verify_agent (similar role, shared LLM config by default).
    global_review_agent: str = ""

    # Agent runtime budgets (Phase 1 only covers the codegen / verify real agents).
    # codegen_max_iterations raised to 15: in practice the agent burns 6-8
    # rounds fixing static_check + sandbox errors, and 10 often gets cut
    # just before the final run_in_sandbox call.
    # codegen_max_tokens raised to 200k: large partitions (e.g. req_0 with
    # 1925 -> 81 blocks) plus long block_items data plus a complex QAOA
    # kernel mean the LLM rewrites the whole code block at 2-3k tokens per
    # round; 100k usually hits tokens_exhausted around round 14, leaving
    # common pitfalls like Pauli string labels unresolved.
    codegen_max_iterations: int = 15
    codegen_max_tool_calls: int = 30
    codegen_max_tokens: int = 200_000
    verify_max_iterations: int = 5
    verify_max_tool_calls: int = 15
    verify_max_tokens: int = 20_000
    # global_review is not a true agent (single call_json). max_rounds is
    # the max number of codegen <-> global_review revise loops:
    # 1 = evaluate only, never bounce back (execute runs regardless);
    # 3 = typical; >5 wastes tokens (if the LLM cannot fix feedback in 3
    # passes, more passes will not help).
    global_review_max_rounds: int = 3
