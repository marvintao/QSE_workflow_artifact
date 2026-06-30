"""Pipeline stage: verify — real agent + 6 tools running the dual-gate verdict.

Input: QuantumKernel + GeneratedCode.code + CombinedResult
(.instance + .value).
Output: VerificationStatus + agent rounds + meta.

Gate A (spec alignment) is judged by the agent itself via
read_kernel_spec + read_code.
Gate B (numerical cross-check) calls solve_instance_classically to
fetch a classical reference; within tolerance the agent rules
cross_checked / mismatch / unverified.
"""
import json
import math
from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader

# classical solvers is a soft dependency: when missing, GATE B
# numerical cross-check is unavailable, but verify still runs (the LLM
# calling solve_instance_classically receives an oracle_unavailable
# error; per the verdict_tool rules this usually lands on 'unverified',
# leaving only GATE A's algorithmic-semantics check).
try:
    from quantum_workflow.knowledge.classical import solvers
    _CLASSICAL_AVAILABLE = True
except ImportError:
    solvers = None
    _CLASSICAL_AVAILABLE = False

_NO_ORACLE_ERR = {"error": "classical oracle unavailable in this deployment "
                            "(ablation mode); verdict must rely on GATE A "
                            "(algorithm/semantic match) and fall back to "
                            "'unverified' if numerical check is required"}
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
from quantum_workflow.pipeline.language import LANGUAGE_NAMES
from quantum_workflow.schemas.combined import CombinedResult
from quantum_workflow.schemas.exec import VerificationStatus
from quantum_workflow.schemas.opportunity import QuantumKernel

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR),
                   keep_trailing_newline=True)

_SYSTEM = ("You are a quantum-verification agent. Use the provided tools "
           "to inspect the kernel spec, code, and combined result, then "
           "commit a single verdict via the verdict() tool.")

# Valid strings accepted by verdict (mapped to enums); FAILED is back-filled by the system on agent failure.
_VALID_STATUS = {
    "cross_checked": VerificationStatus.CROSS_CHECKED,
    "unverified": VerificationStatus.UNVERIFIED,
    "mismatch": VerificationStatus.MISMATCH,
    "off_spec": VerificationStatus.OFF_SPEC,
}


def _build_tools(state: dict[str, Any], *, kernel: QuantumKernel,
                 code: str, combined: CombinedResult) -> dict[str, Tool]:
    """Build the 6 verify tools; verdict is terminal."""

    def read_kernel_spec(_args: dict) -> str:
        return json.dumps({
            "algorithm": kernel.algorithm,
            "algorithm_rationale": kernel.algorithm_rationale,
            "subproblem": kernel.subproblem,
            "io_interface": kernel.io_interface,
            "full_scale_qubits": kernel.full_scale_qubits,
            "reduced_qubits": kernel.reduced_qubits,
        }, ensure_ascii=False)

    def read_code(_args: dict) -> str:
        # Defensive: a prompt-termination sentinel embedded in the code would cut off subsequent instructions.
        return code.replace("--- END CODE ---",
                            "--- END CODE (sanitized) ---")

    def read_result_instance(_args: dict) -> str:
        return json.dumps(combined.instance, ensure_ascii=False)

    def read_result_value(_args: dict) -> str:
        return json.dumps(combined.value, ensure_ascii=False)

    def solve_instance_classically(_args: dict) -> str:
        if solvers is None:
            return json.dumps(_NO_ORACLE_ERR)
        try:
            ref = solvers.solve_instance(combined.instance)
        except (ValueError, KeyError, TypeError) as e:
            return json.dumps({"error": f"{type(e).__name__}: {e}"})
        if not math.isfinite(ref):
            return json.dumps({"error": "non-finite reference"})
        return json.dumps({"value": float(ref)})

    def verdict(args: dict) -> str:
        status = args.get("status", "")
        reason = args.get("reason", "")
        if status not in _VALID_STATUS:
            return (f"error: status must be one of "
                    f"{sorted(_VALID_STATUS)}; got {status!r}")
        # First verdict wins; subsequent calls do not overwrite.
        state.setdefault("verdict", _VALID_STATUS[status])
        state.setdefault("verdict_reason", str(reason))
        return "ok"

    def _empty() -> dict:
        return {"type": "object", "properties": {}, "additionalProperties": False}

    return {
        "read_kernel_spec": Tool(
            name="read_kernel_spec",
            description="Return the full quantum-kernel spec under test.",
            parameters_schema=_empty(), run=read_kernel_spec),
        "read_code": Tool(
            name="read_code",
            description="Return the Python program that produced the result.",
            parameters_schema=_empty(), run=read_code),
        "read_result_instance": Tool(
            name="read_result_instance",
            description="Return the combined result's original instance "
                        "(JSON).",
            parameters_schema=_empty(), run=read_result_instance),
        "read_result_value": Tool(
            name="read_result_value",
            description="Return the combined numerical value (JSON).",
            parameters_schema=_empty(), run=read_result_value),
        "solve_instance_classically": Tool(
            name="solve_instance_classically",
            description="Compute the classical exact reference for the "
                        "result instance. Returns {value} or {error}.",
            parameters_schema=_empty(),
            run=solve_instance_classically),
        "verdict": Tool(
            name="verdict",
            description="TERMINAL. Commit one verdict and STOP. status MUST "
                        "be one of 'cross_checked', 'unverified', "
                        "'mismatch', 'off_spec'.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string",
                                "enum": list(_VALID_STATUS.keys())},
                    "reason": {"type": "string"},
                },
                "required": ["status", "reason"]}, run=verdict),
    }


def _build_sdk_tools(state: dict[str, Any], *, kernel: QuantumKernel,
                      code: str, combined: CombinedResult):
    """SDK MCP version of the 6 verify tools. verdict is terminal (state["verdict"])."""
    from claude_agent_sdk import tool

    @tool("read_kernel_spec",
          "Return the full quantum-kernel spec under test.", {})
    async def read_kernel_spec(_args):
        payload = json.dumps({
            "algorithm": kernel.algorithm,
            "algorithm_rationale": kernel.algorithm_rationale,
            "subproblem": kernel.subproblem,
            "io_interface": kernel.io_interface,
            "full_scale_qubits": kernel.full_scale_qubits,
            "reduced_qubits": kernel.reduced_qubits,
        }, ensure_ascii=False)
        return {"content": [{"type": "text", "text": payload}]}

    @tool("read_code",
          "Return the Python program that produced the result.", {})
    async def read_code(_args):
        text = code.replace("--- END CODE ---",
                            "--- END CODE (sanitized) ---")
        return {"content": [{"type": "text", "text": text}]}

    @tool("read_result_instance",
          "Return the combined result's original instance (JSON).", {})
    async def read_instance(_args):
        return {"content": [{"type": "text",
                              "text": json.dumps(combined.instance,
                                                  ensure_ascii=False)}]}

    @tool("read_result_value",
          "Return the combined numerical value (JSON).", {})
    async def read_value(_args):
        return {"content": [{"type": "text",
                              "text": json.dumps(combined.value,
                                                  ensure_ascii=False)}]}

    @tool("solve_instance_classically",
          "Compute the classical exact reference for the result instance. "
          "Returns {value} or {error}.", {})
    async def solve_classically(_args):
        if solvers is None:
            return {"content": [{"type": "text",
                                  "text": json.dumps(_NO_ORACLE_ERR)}]}
        try:
            ref = solvers.solve_instance(combined.instance)
        except (ValueError, KeyError, TypeError) as e:
            return {"content": [{"type": "text",
                                  "text": json.dumps({"error":
                                      f"{type(e).__name__}: {e}"})}]}
        if not math.isfinite(ref):
            return {"content": [{"type": "text",
                                  "text": json.dumps({
                                      "error": "non-finite reference"})}]}
        return {"content": [{"type": "text",
                              "text": json.dumps({"value": float(ref)})}]}

    @tool("verdict",
          "TERMINAL. Commit one verdict and STOP. status MUST be one of "
          "'cross_checked', 'unverified', 'mismatch', 'off_spec'.",
          {"status": str, "reason": str})
    async def verdict_tool(args):
        status = args.get("status", "")
        reason = args.get("reason", "")
        if status not in _VALID_STATUS:
            return {"content": [{"type": "text",
                                  "text": (f"error: status must be one of "
                                           f"{sorted(_VALID_STATUS)}; "
                                           f"got {status!r}")}]}
        state.setdefault("verdict", _VALID_STATUS[status])
        state.setdefault("verdict_reason", str(reason))
        return {"content": [{"type": "text", "text": "ok"}]}

    return [read_kernel_spec, read_code, read_instance, read_value,
            solve_classically, verdict_tool]


class StageVerify:
    """verify real agent: 5 read tools to investigate + 1 verdict tool to commit."""

    def __init__(self, llm, model_name: str,
                 max_iterations: int, max_tool_calls: int, max_tokens: int):
        """Initialize the verify agent.

        Args:
            llm: Must implement call_with_tools().
            model_name: Model identifier written into metadata.
            max_iterations / max_tool_calls / max_tokens: agent budgets.
        """
        self.llm = llm
        self.model_name = model_name
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.max_tokens = max_tokens

    def run(self, *, kernel: QuantumKernel, code: str,
            combined: CombinedResult,
            language: Literal["en", "zh"] = "en"
            ) -> tuple[VerificationStatus, list[AgentRound], dict]:
        """Run the agent until verdict is committed or the budget is exhausted.

        If the agent never calls verdict within budget, return FAILED
        (assigned by the system).
        """
        tmpl = _env.get_template("stage_verify_agent.jinja")
        user = tmpl.render(kernel=kernel,
                           language_name=LANGUAGE_NAMES[language])

        state: dict[str, Any] = {}

        if isinstance(self.llm, ClaudeSDKClient):
            # SDK path: wrap the 6 verify tools in an in-process MCP server.
            sdk_tools = _build_sdk_tools(state, kernel=kernel, code=code,
                                          combined=combined)
            runner = ClaudeSDKAgentRunner(
                model=self.llm.model, max_rounds=self.max_iterations)
            try:
                final_text, rounds, usage = runner.run(
                    system=_SYSTEM, user=user, tools=sdk_tools,
                    server_name="verify")
            except SDKAgentFailure as e:
                # SDK exception: preserve partial rounds and use a meta
                # shape compatible with the legacy path, so the upper
                # stage trace still records intermediate verify rounds.
                # verdict degrades to FAILED (agent never committed).
                meta = {
                    "llm_input": {"system": _SYSTEM, "user": user},
                    "llm_output": {
                        "verdict": VerificationStatus.FAILED.value,
                        "reason": f"SDK agent failed: {e}",
                        "via": "claude_sdk_agent",
                    },
                    "tokens": e.usage,
                    "model": self.llm.model,
                }
                return VerificationStatus.FAILED, e.rounds, meta
            status = state.get("verdict", VerificationStatus.FAILED)
            meta = {
                "llm_input": {"system": _SYSTEM, "user": user},
                "llm_output": {
                    "verdict": status.value,
                    "reason": state.get("verdict_reason", ""),
                    "final_text": final_text,
                    "via": "claude_sdk_agent",
                },
                "tokens": usage,
                "model": self.llm.model,
            }
            return status, rounds, meta

        tools = _build_tools(state, kernel=kernel, code=code,
                             combined=combined)
        outcome: AgentOutcome = run_agent(
            llm=self.llm, system_prompt=_SYSTEM, user_prompt=user,
            tools=tools,
            max_iterations=self.max_iterations,
            max_tool_calls=self.max_tool_calls,
            max_tokens=self.max_tokens)

        status = state.get("verdict", VerificationStatus.FAILED)
        meta = {
            "llm_input": {"system": _SYSTEM, "user": user},
            "llm_output": {
                "verdict": status.value,
                "reason": state.get("verdict_reason", ""),
                "final_text": outcome.final_text,
                "failure_reason": outcome.failure_reason,
            },
            "tokens": {"total": outcome.total_tokens},
            "model": self.model_name,
        }
        return status, outcome.rounds, meta
