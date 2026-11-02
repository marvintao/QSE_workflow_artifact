# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Pipeline stage: codegen — real agent + 7 tools running a write -> check -> run -> fix inner loop.

Input: ParsedIntent + QuantumKernel + a quantum BlueprintNode + a
representative sub-problem instance.
Output: GeneratedCode (a Python program that runs in the sandbox) plus
agent rounds.

Phase 1 turns on the real agent runtime; the model decides when to
read knowledge docs, write code, debug, and rewrite.
"""
import json
from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader

# knowledge/ is a soft dependency: codegen still runs when it is
# missing (tools return a degraded text hint and the sandbox runs
# without building_blocks aux_files) — this keeps the "no-knowledge"
# ablation experiment available (deleting / moving knowledge/ and
# restarting backend still serves requests).
try:
    from quantum_workflow.knowledge import blocks, cookbook, environment
    _KNOWLEDGE_AVAILABLE = True
except ImportError:
    blocks = None
    cookbook = None
    environment = None
    _KNOWLEDGE_AVAILABLE = False

_NO_KNOWLEDGE_MSG = ("knowledge module unavailable in this deployment "
                     "(ablation mode). Proceed using only qiskit + numpy + "
                     "scipy + the kernel spec; no helper modules to import.")
from quantum_workflow.llm.agent_runtime import (
    AgentOutcome,
    AgentRound,
    Tool,
    run_agent,
)
from quantum_workflow.llm.claude_sdk_agent import (
    ClaudeSDKAgentRunner,
    SDKAgentFailure,
)
from quantum_workflow.llm.claude_sdk_client import ClaudeSDKClient
from quantum_workflow.llm.protocol import LLMError, strip_code_fences
from quantum_workflow.pipeline.language import LANGUAGE_NAMES
from quantum_workflow.sandbox.executor import SandboxExecutor
from quantum_workflow.sandbox.static_check import (
    UnsafeCodeError,
    check_code_safety,
)
from quantum_workflow.schemas.codegen import CoverageReport, GeneratedCode
from quantum_workflow.schemas.intent import ParsedIntent
from quantum_workflow.schemas.opportunity import QuantumKernel
from quantum_workflow.schemas.plan import BlueprintNode

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR),
                   keep_trailing_newline=True)

_SYSTEM = ("You are a quantum-code authoring agent. Use the provided tools "
           "to write, check, and run a Python program that solves the "
           "quantum kernel below. Stop after run_in_sandbox returns "
           "status='success'.")

_REQUIREMENTS = ["qiskit>=2.0", "qiskit-aer", "numpy", "scipy"]


class CodegenAgentFailure(LLMError):
    """codegen agent exhausted its budget without passing the sandbox.

    Carries the full list of agent rounds + the last code, so the
    orchestrator can persist them into stage_trace (letting the
    inspector inspect every tool call per round). A bare LLMError would
    discard this evidence.
    """
    def __init__(self, message: str, rounds: list[AgentRound],
                 last_code: str, failure_reason: str | None,
                 total_tokens: int):
        super().__init__(message)
        self.rounds = rounds
        self.last_code = last_code
        self.failure_reason = failure_reason
        self.total_tokens = total_tokens


def _build_tools(state: dict[str, Any], sandbox: SandboxExecutor,
                 extra_imports: set[str],
                 aux_files: dict[str, str],
                 sub_instance_env: dict[str, str]) -> dict[str, Tool]:
    """Build the 7 codegen tools; every tool reads/writes the shared state['code'].

    sub_instance_env: the env injected by sandbox calls inside the
    agent (contains `SUB_INSTANCE_JSON`), so the agent writes code that
    reads its instance from the env instead of inlining it — execute
    then reuses the same code with different envs to run N times.
    """

    def read_environment_facts(_args: dict) -> str:
        if environment is None:
            return _NO_KNOWLEDGE_MSG
        return environment.environment_facts()

    def read_qiskit_cookbook(_args: dict) -> str:
        if cookbook is None:
            return _NO_KNOWLEDGE_MSG
        return cookbook.qiskit_cookbook()

    def read_blocks_api(_args: dict) -> str:
        if blocks is None:
            return _NO_KNOWLEDGE_MSG
        return blocks.building_blocks_api()

    def write_kernel_code(args: dict) -> str:
        code = args.get("code", "")
        if not isinstance(code, str) or not code.strip():
            return "error: 'code' must be a non-empty string"
        # Tolerate the LLM wrapping code in fences.
        state["code"] = strip_code_fences(code)
        return "ok"

    def static_check(_args: dict) -> str:
        code = state.get("code")
        if not code:
            return "error: no code stored; call write_kernel_code first"
        try:
            check_code_safety(code, extra_allowed_imports=extra_imports)
        except UnsafeCodeError as e:
            return f"unsafe: {e}"
        return "ok"

    def compile_check(_args: dict) -> str:
        code = state.get("code")
        if not code:
            return "error: no code stored; call write_kernel_code first"
        try:
            compile(code, "<agent_kernel>", "exec")
        except SyntaxError as e:
            # Provide line-number context like static_check so the agent sees +/-3 lines of structure.
            from quantum_workflow.sandbox.static_check import _line_context
            ctx = _line_context(code, e.lineno or 0)
            return (f"syntax_error: {e}\n"
                    f"context (line {e.lineno} ±3):\n{ctx}")
        return "ok"

    def run_in_sandbox(_args: dict) -> str:
        code = state.get("code")
        if not code:
            return json.dumps({"status": "error",
                                "stderr": "no code stored"})
        # Once the sandbox succeeds, record the status in state for
        # outcome judgment. The env injects SUB_INSTANCE_JSON so the
        # code can read its instance from the env.
        out = sandbox.run(code, aux_files=aux_files, env=sub_instance_env)
        if out.get("status") == "success":
            state["sandbox_ok"] = True
        # Tool output is a JSON string; the runtime auto-truncates long stderr.
        return json.dumps({
            "status": out.get("status"),
            "result": out.get("result"),
            "stderr": out.get("stderr_excerpt"),
        }, ensure_ascii=False)

    def _empty() -> dict:
        return {"type": "object", "properties": {}, "additionalProperties": False}

    return {
        "read_environment_facts": Tool(
            name="read_environment_facts",
            description="Return Python/Qiskit env facts + allowed imports.",
            parameters_schema=_empty(), run=read_environment_facts),
        "read_qiskit_cookbook": Tool(
            name="read_qiskit_cookbook",
            description="Return the Qiskit 2.x usage cookbook.",
            parameters_schema=_empty(), run=read_qiskit_cookbook),
        "read_blocks_api": Tool(
            name="read_blocks_api",
            description="Return names+signatures of pre-installed numerical "
                        "building-blocks the program may import.",
            parameters_schema=_empty(), run=read_blocks_api),
        "write_kernel_code": Tool(
            name="write_kernel_code",
            description="Store/overwrite the full Python program in agent "
                        "state. Required before any check.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string",
                             "description": "Complete program source"}},
                "required": ["code"]}, run=write_kernel_code),
        "static_check": Tool(
            name="static_check",
            description="Run AST safety check on the stored code.",
            parameters_schema=_empty(), run=static_check),
        "compile_check": Tool(
            name="compile_check",
            description="Compile() the stored code; surfaces SyntaxError.",
            parameters_schema=_empty(), run=compile_check),
        "run_in_sandbox": Tool(
            name="run_in_sandbox",
            description="Execute the stored code under rlimit sandbox; "
                        "returns JSON {status,result,stderr}. status='success'"
                        " means the program finished cleanly.",
            parameters_schema=_empty(), run=run_in_sandbox),
    }


def _build_sdk_tools(state, sandbox, extra_imports, aux_files,
                      sub_instance_env):
    """SDK MCP version of the 7 codegen tools (@tool-decorated async functions).

    Implementation reuses the legacy-path helpers:
    environment.environment_facts() / cookbook.qiskit_cookbook() /
    blocks.building_blocks_api() / check_code_safety / sandbox.run.
    state / sandbox / extra_imports / aux_files / sub_instance_env are
    shared via closures.

    SDK MCP tool handlers return a dict
    {"content": [{"type": "text", "text": ...}]}.
    """
    # Import SDK lazily so importing stage_codegen does not force a hard
    # SDK dependency (the legacy path does not need the SDK installed).
    from claude_agent_sdk import tool

    @tool("read_environment_facts",
          "Return Python/Qiskit env facts + allowed imports.", {})
    async def read_facts(_args):
        text = (environment.environment_facts() if environment is not None
                else _NO_KNOWLEDGE_MSG)
        return {"content": [{"type": "text", "text": text}]}

    @tool("read_qiskit_cookbook",
          "Return the Qiskit 2.x usage cookbook.", {})
    async def read_cookbook(_args):
        text = (cookbook.qiskit_cookbook() if cookbook is not None
                else _NO_KNOWLEDGE_MSG)
        return {"content": [{"type": "text", "text": text}]}

    @tool("read_blocks_api",
          "Return names+signatures of pre-installed numerical "
          "building-blocks the program may import.", {})
    async def read_blocks(_args):
        text = (blocks.building_blocks_api() if blocks is not None
                else _NO_KNOWLEDGE_MSG)
        return {"content": [{"type": "text", "text": text}]}

    @tool("write_kernel_code",
          "Store/overwrite the full Python program in agent state. "
          "Required before any check.",
          {"code": str})
    async def write_code(args):
        code = args.get("code", "")
        if not isinstance(code, str) or not code.strip():
            return {"content": [{"type": "text",
                                  "text": "error: 'code' must be a "
                                          "non-empty string"}]}
        state["code"] = strip_code_fences(code)
        return {"content": [{"type": "text", "text": "ok"}]}

    @tool("static_check",
          "Run AST safety check on the stored code.", {})
    async def static(_args):
        code = state.get("code")
        if not code:
            return {"content": [{"type": "text",
                                  "text": "error: no code stored; call "
                                          "write_kernel_code first"}]}
        try:
            check_code_safety(code, extra_allowed_imports=extra_imports)
        except UnsafeCodeError as e:
            return {"content": [{"type": "text",
                                  "text": f"unsafe: {e}"}]}
        return {"content": [{"type": "text", "text": "ok"}]}

    @tool("compile_check",
          "Compile() the stored code; surfaces SyntaxError with ±3-line "
          "context.", {})
    async def compile_tool(_args):
        code = state.get("code")
        if not code:
            return {"content": [{"type": "text",
                                  "text": "error: no code stored; call "
                                          "write_kernel_code first"}]}
        try:
            compile(code, "<agent_kernel>", "exec")
        except SyntaxError as e:
            from quantum_workflow.sandbox.static_check import _line_context
            ctx = _line_context(code, e.lineno or 0)
            return {"content": [{"type": "text",
                                  "text": (f"syntax_error: {e}\n"
                                           f"context (line {e.lineno} ±3):"
                                           f"\n{ctx}")}]}
        return {"content": [{"type": "text", "text": "ok"}]}

    @tool("run_in_sandbox",
          "Execute the stored code under rlimit and return JSON "
          "{status, result, stderr}. status='success' means code ran clean.",
          {})
    async def run_sandbox_tool(_args):
        code = state.get("code")
        if not code:
            return {"content": [{"type": "text",
                                  "text": json.dumps({
                                      "status": "error",
                                      "stderr": "no code stored"})}]}
        out = sandbox.run(code, aux_files=aux_files, env=sub_instance_env)
        if out.get("status") == "success":
            state["sandbox_ok"] = True
        return {"content": [{"type": "text",
                              "text": json.dumps({
                                  "status": out.get("status"),
                                  "result": out.get("result"),
                                  "stderr": out.get("stderr_excerpt"),
                              }, ensure_ascii=False)}]}

    return [read_facts, read_cookbook, read_blocks, write_code,
            static, compile_tool, run_sandbox_tool]


class StageCodegen:
    """codegen real agent: writes runnable code via a 7-tool write -> check -> run -> fix inner loop."""

    def __init__(self, llm, model_name: str, sandbox: SandboxExecutor,
                 max_iterations: int, max_tool_calls: int, max_tokens: int):
        """Initialize the codegen agent.

        Args:
            llm: Must implement call_with_tools().
            model_name: Model identifier written into metadata.
            sandbox: Sandbox executor (for the run_in_sandbox tool).
            max_iterations / max_tool_calls / max_tokens: agent budgets.
        """
        self.llm = llm
        self.model_name = model_name
        self.sandbox = sandbox
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.max_tokens = max_tokens

    def run(self, *, intent: ParsedIntent, kernel: QuantumKernel,
            node: BlueprintNode, sub_problem_instance: dict[str, Any],
            language: Literal["en", "zh"] = "en",
            prior_review_feedback: str = ""
            ) -> tuple[GeneratedCode, list[AgentRound], dict]:
        """Run the agent until the sandbox passes or the budget is exhausted; return (GeneratedCode, rounds, meta).

        Args:
            prior_review_feedback: When global_review bounces back with
                `revise`, the reviewer's concrete change requests are
                injected as a preceding instruction in the prompt so the
                LLM knows why the previous code was rejected and which
                direction to fix. Empty string means normal first-pass
                codegen.
        """
        tmpl = _env.get_template("stage_codegen_agent.jinja")
        user = tmpl.render(
            intent=intent, kernel=kernel, node=node,
            sub_problem_instance_json=json.dumps(
                sub_problem_instance, ensure_ascii=False, indent=2),
            language_name=LANGUAGE_NAMES[language],
            prior_review_feedback=prior_review_feedback)

        state: dict[str, Any] = {"code": None, "sandbox_ok": False}
        # When the knowledge package is missing, do not ship
        # building_blocks aux files into the sandbox; if the
        # LLM-generated code tries `import qaoa_blocks` it raises
        # ImportError, run_in_sandbox surfaces the stderr, and the LLM
        # adjusts on its own.
        aux_files = (blocks.building_block_files()
                      if blocks is not None else {})
        extra_imports = (blocks.building_block_module_names()
                          if blocks is not None else set())
        sub_instance_env = {
            "SUB_INSTANCE_JSON": json.dumps(sub_problem_instance,
                                              ensure_ascii=False),
        }

        # SDK path (LLM is ClaudeSDKClient): use the SDK's built-in
        # agent loop + an in-process MCP server to host tools, instead
        # of our own AgenticRuntime. ClaudeSDKClient.call_with_tools
        # raises NotImplementedError, so we bypass it and hand the
        # model name directly to ClaudeSDKAgentRunner.
        if isinstance(self.llm, ClaudeSDKClient):
            return self._run_sdk(
                system=_SYSTEM, user=user, node=node, state=state,
                aux_files=aux_files, extra_imports=extra_imports,
                sub_instance_env=sub_instance_env)

        tools = _build_tools(state, self.sandbox, extra_imports, aux_files,
                              sub_instance_env)

        outcome: AgentOutcome = run_agent(
            llm=self.llm, system_prompt=_SYSTEM, user_prompt=user,
            tools=tools,
            max_iterations=self.max_iterations,
            max_tool_calls=self.max_tool_calls,
            max_tokens=self.max_tokens)

        if not state.get("sandbox_ok"):
            # On failure expose every round's tool calls too, so we can debug where the agent got stuck.
            raise CodegenAgentFailure(
                f"codegen agent did not reach sandbox success "
                f"(reason={outcome.failure_reason or 'unfinished'}; "
                f"rounds={len(outcome.rounds)})",
                rounds=outcome.rounds,
                last_code=state.get("code") or "",
                failure_reason=outcome.failure_reason,
                total_tokens=outcome.total_tokens,
            )
        code = state["code"] or ""
        generated = GeneratedCode(
            code=code, entry_point="main",
            requirements=list(_REQUIREMENTS),
            coverage=CoverageReport(planned_nodes=[node.id],
                                    covered_nodes=[node.id]),
            aux_files=aux_files)
        meta = {
            "llm_input": {"system": _SYSTEM, "user": user},
            "llm_output": {"code": code,
                           "final_text": outcome.final_text,
                           "failure_reason": outcome.failure_reason},
            "tokens": {"total": outcome.total_tokens},
            "model": self.model_name,
        }
        return generated, outcome.rounds, meta

    # ---------- SDK path (ClaudeSDKClient) ----------

    def _run_sdk(self, *, system, user, node, state,
                  aux_files, extra_imports, sub_instance_env):
        """Use the Claude Agent SDK's built-in agent loop with an in-process MCP server.

        Tool implementations match the legacy path (state closure /
        sandbox / extra_imports / aux_files / env shared); they are
        just wrapped as SDK `@tool` callables.
        """
        sdk_tools = _build_sdk_tools(
            state, self.sandbox, extra_imports, aux_files, sub_instance_env)
        runner = ClaudeSDKAgentRunner(
            model=self.llm.model, max_rounds=self.max_iterations)
        try:
            final_text, rounds, usage = runner.run(
                system=system, user=user, tools=sdk_tools,
                server_name="codegen")
        except SDKAgentFailure as e:
            # SDK exception (max_turns / rate_limit / unknown): rounds
            # are already carried back; raise CodegenAgentFailure so the
            # orchestrator preserves every round's tool call when
            # writing the trace (otherwise trace.rounds=0, making the
            # failure unanalyzable).
            raise CodegenAgentFailure(
                f"codegen agent (SDK) failed: {e}",
                rounds=e.rounds,
                last_code=state.get("code") or "",
                failure_reason="sdk_agent_error",
                total_tokens=e.usage.get("input_tokens", 0)
                              + e.usage.get("output_tokens", 0)) from e

        if not state.get("sandbox_ok"):
            raise CodegenAgentFailure(
                f"codegen agent did not reach sandbox success "
                f"(reason=iterations_exhausted; rounds={len(rounds)})",
                rounds=rounds,
                last_code=state.get("code") or "",
                failure_reason="iterations_exhausted",
                total_tokens=usage.get("input_tokens", 0)
                              + usage.get("output_tokens", 0))

        code = state["code"]
        generated = GeneratedCode(
            code=code,
            requirements=list(_REQUIREMENTS),
            coverage=CoverageReport(planned_nodes=[node.id],
                                    covered_nodes=[node.id]),
            aux_files=aux_files)
        meta = {
            "llm_input": {"system": system, "user": user},
            "llm_output": {"code": code, "final_text": final_text,
                           "via": "claude_sdk_agent"},
            "tokens": usage,
            "model": self.llm.model,
        }
        return generated, rounds, meta
