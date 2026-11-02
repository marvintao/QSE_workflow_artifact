# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""
Pipeline stage 3: hybrid workflow blueprint.

Input: structured ParsedIntent + QuantumOpportunity.
Output: WorkflowBlueprint (nodes tagged classical/quantum).

The LLM lays out the end-to-end DAG: classical nodes describe only the
interface, not the implementation; quantum nodes correspond to the
quantum kernel. Replaces the old Stage3Workflow.
"""
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader

from quantum_workflow.llm.retry import call_with_validation
from quantum_workflow.pipeline.language import LANGUAGE_NAMES
from quantum_workflow.schemas.intent import ParsedIntent
from quantum_workflow.schemas.opportunity import QuantumOpportunity
from quantum_workflow.schemas.plan import (
    BlueprintEdge,
    BlueprintNode,
    Feasibility,
    WorkflowBlueprint,
)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR),
                   keep_trailing_newline=True)

_SYSTEM = ("You are a hybrid quantum-classical workflow designer. "
           "Always respond with strict JSON, no prose.")


class Stage3Blueprint:
    """Stage 3: the LLM designs a classical + quantum hybrid workflow blueprint."""

    def __init__(self, llm, model_name: str):
        """Initialize the hybrid-blueprint stage.

        Args:
            llm: LLM adapter that must implement call_json().
            model_name: Model identifier written into trace metadata.
        """
        self.llm = llm
        self.model_name = model_name

    def run(self, *, intent: ParsedIntent, opportunity: QuantumOpportunity,
            language: Literal["en", "zh"] = "en"
            ) -> tuple[WorkflowBlueprint, dict]:
        """Design the hybrid blueprint from intent + quantum opportunity; return WorkflowBlueprint plus metadata."""
        tmpl = _env.get_template("stage3_blueprint.jinja")
        user = tmpl.render(intent=intent, opportunity=opportunity,
                           language_name=LANGUAGE_NAMES[language])

        def _llm_call(prompt: str):
            return self.llm.call_json(system=_SYSTEM, user=prompt,
                                      cache_system=True)

        def _validate(raw: dict) -> WorkflowBlueprint:
            """Construct a WorkflowBlueprint from the LLM output; raise on malformed structure to trigger retry."""
            return WorkflowBlueprint(
                nodes=[BlueprintNode(**n) for n in raw["nodes"]],
                edges=[BlueprintEdge(**e) for e in raw.get("edges", [])],
                feasibility=Feasibility(**raw["feasibility"]))

        blueprint, usage, raws = call_with_validation(
            llm_call=_llm_call, validate=_validate, base_user_prompt=user)
        meta = {
            "llm_input": {"system": _SYSTEM, "user": user},
            "llm_output": {"artifact": blueprint.model_dump(),
                           "raw_attempts": raws},
            "tokens": usage,
            "model": self.model_name,
        }
        return blueprint, meta
