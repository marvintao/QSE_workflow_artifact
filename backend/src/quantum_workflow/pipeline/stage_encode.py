"""Pipeline stage: encode — decompose the full-scale problem into sub-problems that fit the feasible budget.

Phase 1 is a single-LLM-call version (Phase 2 upgrades to a real agent
with tools).
Input: ParsedIntent + QuantumOpportunity + WorkflowBlueprint.
Output: EncodingPlan (sub-problem list + combine plan).
"""
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader

from quantum_workflow.llm.retry import call_with_validation
from quantum_workflow.pipeline.language import LANGUAGE_NAMES
from quantum_workflow.schemas.encoding import (
    EncodingPlan,
    PartitionSpec,
    SubProblem,
)
from quantum_workflow.schemas.intent import ParsedIntent
from quantum_workflow.schemas.opportunity import QuantumOpportunity
from quantum_workflow.schemas.plan import WorkflowBlueprint

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR),
                   keep_trailing_newline=True)

_SYSTEM = ("You are a quantum-problem decomposer. "
           "Always respond with strict JSON, no prose.")


class StageEncode:
    """encode stage: the LLM decides the decomposition strategy and produces an EncodingPlan."""

    def __init__(self, llm, model_name: str):
        """Initialize the encode stage.

        Args:
            llm: LLM adapter that must implement call_json().
            model_name: Model identifier written into trace metadata.
        """
        self.llm = llm
        self.model_name = model_name

    def run(self, *, intent: ParsedIntent, opportunity: QuantumOpportunity,
            blueprint: WorkflowBlueprint,
            language: Literal["en", "zh"] = "en"
            ) -> tuple[EncodingPlan, dict]:
        """Produce an EncodingPlan; return (plan, meta)."""
        tmpl = _env.get_template("stage_encode.jinja")
        user = tmpl.render(intent=intent, opportunity=opportunity,
                           blueprint=blueprint,
                           language_name=LANGUAGE_NAMES[language])

        def _llm_call(prompt: str):
            return self.llm.call_json(system=_SYSTEM, user=prompt,
                                      cache_system=True)

        def _validate(raw: dict) -> EncodingPlan:
            """Build an EncodingPlan from the LLM output; raise on malformed structure to trigger retry.

            Supports two output forms: a sub_problems list (small scale)
            or partition_spec metadata (large scale, expanded by Python
            later); exactly one must be non-empty.
            """
            sps_raw = raw.get("sub_problems") or []
            spec_raw = raw.get("partition_spec")
            return EncodingPlan(
                strategy=raw["strategy"],
                strategy_rationale=raw["strategy_rationale"],
                sub_problems=[SubProblem(**sp) for sp in sps_raw],
                partition_spec=(PartitionSpec(**spec_raw) if spec_raw else None),
                combine_method=raw["combine_method"],
            )

        plan, usage, raws = call_with_validation(
            llm_call=_llm_call, validate=_validate, base_user_prompt=user)
        meta = {
            "llm_input": {"system": _SYSTEM, "user": user},
            "llm_output": {"artifact": plan.model_dump(),
                           "raw_attempts": raws},
            "tokens": usage,
            "model": self.model_name,
        }
        return plan, meta
