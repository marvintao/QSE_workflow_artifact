"""global_review stage: between codegen and execute, check whether the code satisfies the original requirement.

Motivation: the codegen agent only sees the kernel spec, so it can
produce code that technically runs (static + compile + sandbox all
pass) but **does not solve the actual user requirement** — e.g. it
submits a `print('hello')` stub, picks the wrong algorithm, or its
objective drifts from the requirement. global_review reads across
stages (intent / kernel / blueprint / encode / code), emits approve /
revise + feedback, and bounces back to codegen on revise.
"""
import json
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader

from quantum_workflow.llm.retry import call_with_validation
from quantum_workflow.pipeline.language import LANGUAGE_NAMES
from quantum_workflow.schemas.encoding import EncodingPlan
from quantum_workflow.schemas.global_review import GlobalReviewResult
from quantum_workflow.schemas.intent import ParsedIntent
from quantum_workflow.schemas.opportunity import QuantumKernel
from quantum_workflow.schemas.plan import WorkflowBlueprint

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR),
                   keep_trailing_newline=True)

_SYSTEM = (
    "You are a global reviewer for a quantum workflow pipeline. "
    "Always respond with strict JSON, no prose."
)


class StageGlobalReview:
    """global review stage: compare code against requirement and emit approve / revise + feedback."""

    def __init__(self, llm, model_name: str):
        """Initialize the global-review stage.

        Args:
            llm: LLM adapter that must implement call_json().
            model_name: Model identifier written into trace metadata.
        """
        self.llm = llm
        self.model_name = model_name

    def run(self, *,
            user_requirement: str,
            intent: ParsedIntent,
            kernel: QuantumKernel,
            blueprint: WorkflowBlueprint,
            encoding_plan: EncodingPlan,
            code: str,
            prior_feedback: str = "",
            language: Literal["en", "zh"] = "en"
            ) -> tuple[GlobalReviewResult, dict]:
        """Run a single global-review round; return (result, meta).

        Args:
            user_requirement: Original user input text (raw_text).
            intent / kernel / blueprint / encoding_plan: outputs of the
                upstream 4 stages.
            code: Code currently produced by codegen.
            prior_feedback: The previous round's revise feedback (if
                any), so the reviewer can judge whether codegen got it
                right this time.
            language: Language code (en/zh).
        """
        # Pick the quantum node's description from the blueprint (so the reviewer sees what codegen was supposed to do).
        node_desc = ""
        for n in blueprint.nodes:
            if n.kind == "quantum":
                node_desc = n.description
                break
        # sample instance: the first sub_problem's instance (enough for shape inference; do not send the full data).
        sample_inst = (encoding_plan.sub_problems[0].instance
                        if encoding_plan.sub_problems else {})
        tmpl = _env.get_template("stage_global_review.jinja")
        user = tmpl.render(
            user_requirement=user_requirement,
            intent=intent,
            kernel=kernel,
            blueprint_node_description=node_desc,
            encoding_plan=encoding_plan,
            sample_instance_json=json.dumps(sample_inst, ensure_ascii=False,
                                              indent=2),
            code=code,
            prior_feedback=prior_feedback,
            language_name=LANGUAGE_NAMES[language],
        )

        def _llm_call(prompt: str):
            return self.llm.call_json(system=_SYSTEM, user=prompt,
                                      cache_system=True)

        def _validate(raw: dict) -> GlobalReviewResult:
            result = GlobalReviewResult(**raw)
            # revise must come with concrete feedback; bouncing back to codegen with empty feedback is pointless.
            if result.verdict == "revise" and not result.feedback.strip():
                raise ValueError(
                    "global_review: verdict=revise but feedback is empty — "
                    "reviewer must name specific code change for codegen"
                )
            return result

        result, usage, raws = call_with_validation(
            llm_call=_llm_call, validate=_validate, base_user_prompt=user)
        meta = {
            "llm_input": {"system": _SYSTEM, "user": user},
            "llm_output": {"artifact": result.model_dump(),
                           "raw_attempts": raws},
            "tokens": usage,
            "model": self.model_name,
        }
        return result, meta
