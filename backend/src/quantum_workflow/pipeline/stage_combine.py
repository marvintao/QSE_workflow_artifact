"""Pipeline stage: combine — merge N sub-circuit results into a complete solution for the original problem.

Phase 1 single-LLM-call version (Phase 2 upgrades to a real agent with tools).
Input: EncodingPlan + original instance + list of sub-results.
Output: CombinedResult (verify cross-checks against its .instance + .value).
"""
import json
from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader

from quantum_workflow.llm.retry import call_with_validation
from quantum_workflow.pipeline.language import LANGUAGE_NAMES
from quantum_workflow.schemas.combined import CombinedResult
from quantum_workflow.schemas.encoding import EncodingPlan

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR),
                   keep_trailing_newline=True)

_SYSTEM = ("You are a quantum sub-result aggregator. "
           "Always respond with strict JSON, no prose.")


class StageCombine:
    """combine stage: aggregate sub-results according to EncodingPlan.combine_method."""

    def __init__(self, llm, model_name: str):
        """Initialize the combine stage.

        Args:
            llm: LLM adapter that must implement call_json().
            model_name: Model identifier written into trace metadata.
        """
        self.llm = llm
        self.model_name = model_name

    def run(self, *, encoding_plan: EncodingPlan,
            original_instance: dict[str, Any],
            sub_results: list[dict[str, Any]],
            language: Literal["en", "zh"] = "en"
            ) -> tuple[CombinedResult, dict]:
        """Merge sub-results and return (CombinedResult, meta).

        Each entry in sub_results has shape
        {"id": "sp-N", "role": "...", "value": ...}.
        """
        # Per-item rendering: convert value to a JSON string so the template never sees a Python repr.
        rendered_subs = [
            {"id": sr["id"], "role": sr.get("role", ""),
             "value_json": json.dumps(sr.get("value"), ensure_ascii=False)}
            for sr in sub_results
        ]
        # The prompt no longer ships all 121 sub_results (the LLM tends
        # to echo them, blowing past max_tokens and truncating the
        # JSON). Send an orchestrator-precomputed summary + head/tail
        # of 5 samples instead. subresults_summary is filled by the
        # orchestrator itself; the LLM is not asked to emit it.
        numeric_values = [sr.get("value") for sr in sub_results
                          if isinstance(sr.get("value"), (int, float))
                          and not isinstance(sr.get("value"), bool)]
        if numeric_values:
            sub_summary = {
                "count": len(sub_results),
                "sum":  float(sum(numeric_values)),
                "mean": float(sum(numeric_values) / len(numeric_values)),
                "min":  float(min(numeric_values)),
                "max":  float(max(numeric_values)),
            }
        else:
            sub_summary = {
                "count": len(sub_results),
                "sum":  None, "mean": None, "min": None, "max": None,
            }
        _HEAD_TAIL = 5
        sub_head = rendered_subs[:_HEAD_TAIL]
        sub_tail = (rendered_subs[-_HEAD_TAIL:]
                    if len(rendered_subs) > _HEAD_TAIL else [])

        tmpl = _env.get_template("stage_combine.jinja")
        user = tmpl.render(
            encoding_plan=encoding_plan,
            original_instance_json=json.dumps(original_instance,
                                              ensure_ascii=False, indent=2),
            sub_summary=sub_summary,
            sub_head=sub_head,
            sub_tail=sub_tail,
            language_name=LANGUAGE_NAMES[language],
        )

        def _llm_call(prompt: str):
            return self.llm.call_json(system=_SYSTEM, user=prompt,
                                      cache_system=True)

        def _validate(raw: dict) -> CombinedResult:
            """Build a CombinedResult; subresults_summary is filled by the orchestrator and `instance` must equal the original instance verbatim (guards against LLM drift)."""
            # The LLM is prompted not to emit subresults_summary; we fill it ourselves.
            raw_no_sub = {k: v for k, v in raw.items()
                          if k != "subresults_summary"}
            cr = CombinedResult(**raw_no_sub)
            if cr.instance != original_instance:
                raise ValueError(
                    "combine: result.instance != original_instance — "
                    "must be copied verbatim")
            cr.subresults_summary = [
                {"id": sr["id"], "value": sr.get("value")}
                for sr in sub_results
            ]
            return cr

        combined, usage, raws = call_with_validation(
            llm_call=_llm_call, validate=_validate, base_user_prompt=user)
        meta = {
            "llm_input": {"system": _SYSTEM, "user": user},
            "llm_output": {"artifact": combined.model_dump(),
                           "raw_attempts": raws},
            "tokens": usage,
            "model": self.model_name,
        }
        return combined, meta
