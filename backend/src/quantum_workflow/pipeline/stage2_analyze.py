"""
Pipeline stage 2: quantum-opportunity analysis.

Input: structured ParsedIntent.
Output: QuantumOpportunity.

The LLM decomposes the problem, identifies a quantum-amenable kernel,
picks the algorithm itself, and estimates scale. Algorithm choice is
fully delegated to the LLM; the system does not maintain an algorithm
catalog. Replaces the old Stage2SolutionDesign.
"""
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader

from quantum_workflow.llm.retry import call_with_validation
from quantum_workflow.pipeline.language import LANGUAGE_NAMES
from quantum_workflow.schemas.intent import ParsedIntent
from quantum_workflow.schemas.opportunity import QuantumOpportunity

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR),
                   keep_trailing_newline=True)

_SYSTEM = ("You are a quantum-computing solution architect. "
           "Always respond with strict JSON, no prose.")


def _summarize_instance_data(instance_data: list | dict | None) -> str:
    """Summarize instance_data as a schema sample (first 2 items + total length) so the analyze-stage LLM can infer the real data shape.

    The full list (potentially 1000+ items) is never sent — it would
    blow the token budget.
    """
    if instance_data is None:
        return "(parse stage extracted no instance_data — base subproblem on "
        "problem_statement alone)"
    if isinstance(instance_data, list):
        n = len(instance_data)
        head = instance_data[:2]
        import json
        return (f"instance_data is a LIST of {n} items. First 2 items "
                f"(use these to infer schema, NOT to enumerate; the "
                f"subproblem must work for all {n}):\n"
                f"{json.dumps(head, ensure_ascii=False, indent=2)}")
    if isinstance(instance_data, dict):
        import json
        keys = list(instance_data.keys())
        return (f"instance_data is a DICT with top-level keys: {keys}. "
                f"Full content (truncated to 2000 chars):\n"
                f"{json.dumps(instance_data, ensure_ascii=False)[:2000]}")
    return f"(unexpected instance_data type: {type(instance_data).__name__})"


class Stage2Analyze:
    """Stage 2: the LLM decomposes the problem and identifies the quantum kernel."""

    def __init__(self, llm, model_name: str, feasible_qubits: int):
        """Initialize the quantum-opportunity analysis stage.

        Args:
            llm: LLM adapter that must implement call_json().
            model_name: Model identifier written into trace metadata.
            feasible_qubits: Simulator-feasible qubit budget injected
                into the prompt for scale estimation.
        """
        self.llm = llm
        self.model_name = model_name
        self.feasible_qubits = feasible_qubits

    def run(self, *, intent: ParsedIntent,
            language: Literal["en", "zh"] = "en"
            ) -> tuple[QuantumOpportunity, dict]:
        """Analyze quantum opportunity; return QuantumOpportunity plus LLM-call metadata."""
        # Pass the first 2 items of instance_data as a schema sample to
        # the LLM so it picks ONE concrete implementation path based on
        # the actual data shape (scalar-per-item vs pairwise matrix vs
        # dict-of-arrays) instead of writing "X or Y" ambiguity that
        # downstream codegen / verify each interpret differently. The
        # full data can be N=10k; the first 2 items are enough for
        # schema inference.
        schema_sample = _summarize_instance_data(intent.instance_data)

        tmpl = _env.get_template("stage2_analyze.jinja")
        user = tmpl.render(intent=intent,
                           instance_data_schema=schema_sample,
                           feasible_qubits=self.feasible_qubits,
                           language_name=LANGUAGE_NAMES[language])

        def _llm_call(prompt: str):
            return self.llm.call_json(system=_SYSTEM, user=prompt,
                                      cache_system=True)

        opportunity, usage, raws = call_with_validation(
            llm_call=_llm_call,
            validate=lambda raw: QuantumOpportunity(**raw),
            base_user_prompt=user)
        meta = {
            "llm_input": {"system": _SYSTEM, "user": user},
            "llm_output": {"artifact": opportunity.model_dump(),
                           "raw_attempts": raws},
            "tokens": usage,
            "model": self.model_name,
        }
        return opportunity, meta
