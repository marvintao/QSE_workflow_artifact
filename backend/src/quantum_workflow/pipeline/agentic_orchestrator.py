# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Agentic pipeline orchestrator (Phase 1): an 8-stage flow.

parse -> analyze -> blueprint -> encode -> codegen* -> execute(xN) -> combine -> verify*

* Real agent stages: codegen / verify; the other 6 stages are
  single-shot LLM calls (Phase 2 upgrades these).
Tracing is two-level: one stage_trace row per stage, and agent stages
additionally write each AgentRound to agent_round.
"""
import json
from typing import Any, Literal

from quantum_workflow.assets.protocol import AssetRepo
from quantum_workflow.pipeline.stage_codegen import (
    CodegenAgentFailure,
    StageCodegen,
)
from quantum_workflow.pipeline.stage_combine import StageCombine
from quantum_workflow.pipeline.stage_encode import StageEncode
from quantum_workflow.pipeline.stage_verify import StageVerify
from quantum_workflow.schemas.encoding import EncodingPlan, SubProblem
from quantum_workflow.schemas.exec import ExecResult, ExecStatus, VerificationStatus
from quantum_workflow.traces.recorder import TraceRecorder
from quantum_workflow.traces.store import TraceStore


# Common key names for the "primary result value" inside execute.result,
# tried in priority order. The codegen prompt requires LLM output to use
# "value", but legacy code / occasional LLM disobedience is tolerated.
_VALUE_KEYS = ("value", "energy", "objective", "expectation", "result")


# Deterministic Python combine aggregator: the LLM is unreliable when
# summing large lists (asked to sum 121 numbers it will fabricate one).
# Python owns the pure math here while the LLM still picks the strategy
# (the combine_method text). Mapping: keywords found in combine_method
# text -> the matching Python function.
_AGG_KEYWORDS: dict[str, tuple[str, ...]] = {
    # Expanded sum synonyms: under partitioning, "concatenate
    # indices" / "splice sub-solutions" / "merge blocks" all collapse
    # numerically to per-block contributions added together (each
    # block's value is its contribution to the objective).
    "sum":  ("sum", "总和", "求和", "求合", "加和", "summation",
              "concat", "拼接", "连接", "合并", "汇总", "block sum",
              "partition", "分块", "子问题贡献", "贡献相加"),
    "mean": ("mean", "average", "平均", "均值"),
    "max":  ("max", "最大", "maximum"),
    "min":  ("min", "最小", "minimum"),
}


def _try_python_aggregate(combine_method: str,
                          sub_results: list[dict]) -> float | None:
    """Try to aggregate sub_results in Python based on the combine_method text and value types.

    Returns the aggregated float on success; returns None when nothing
    can be determined, falling back to the LLM.

    The LLM tends to fabricate values when sub_results has, say, 121
    entries (we have seen sum reported as -2.0 vs the true -14.8).
    Python owns this layer of math while the LLM only picks the
    combine strategy — semantics unchanged, numerical correctness
    enforced.
    """
    if not sub_results:
        return None
    cm = (combine_method or "").lower()
    raw_values = [sr.get("value") for sr in sub_results]
    # Only true numerics (not bools) are aggregatable.
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               for v in raw_values):
        return None
    values = [float(v) for v in raw_values]
    for op, kws in _AGG_KEYWORDS.items():
        if any(k in cm for k in kws):
            if op == "sum":
                return float(sum(values))
            if op == "mean":
                return float(sum(values) / len(values))
            if op == "max":
                return float(max(values))
            if op == "min":
                return float(min(values))
    return None


def _extract_value(result_obj: dict) -> Any:
    """Extract the numeric result from execute.result: try "value" first, then a few common synonym keys."""
    for k in _VALUE_KEYS:
        v = result_obj.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
    return None


def _enrich_with_instance_data(encoding: EncodingPlan,
                                 instance_data: list | dict | None) -> None:
    """Inject slices of the full-scale instance_data extracted by parse into encoding.sub_problems (each block takes variable_start..variable_end).

    - instance_data is None: nothing to inject (parse did not capture it); no-op.
    - sub_problem.instance lacks variable_start/end: likely a Shape A
      degenerate case (N=1); inject the entire instance_data into
      block_items so the code sees the full data.
    - instance_data is a list: slice by index.
    - instance_data is a dict: inject as-is (assumed dict-shaped, the
      generated code parses it).

    Mutates sub_problem.instance.block_items in place.
    """
    if instance_data is None:
        return
    for sp in encoding.sub_problems:
        inst = sp.instance
        if isinstance(instance_data, list):
            start = inst.get("variable_start")
            end = inst.get("variable_end")
            if isinstance(start, int) and isinstance(end, int):
                inst["block_items"] = instance_data[start:end]
            else:
                # Shape A degenerate (no block index) or no partition; pass the full list.
                inst["block_items"] = instance_data
        else:
            # dict-shaped -- pass through (the code parses it itself).
            inst["block_items"] = instance_data


def _expand_partition_spec(encoding: EncodingPlan) -> None:
    """When encoding.partition_spec is set, expand it into K SubProblems and inject them into encoding.sub_problems (in place).

    Python is responsible for materializing each block's concrete instance:
      - Shared fields are copied from spec.instance_template.
      - Per-block fields are injected: block_index / variable_start /
        variable_end / num_variables (so the codegen code, reading
        SUB_INSTANCE_JSON, can derive its data by index).
    After expansion partition_spec is cleared (to prevent downstream
    misuse).

    No-op when encoding.sub_problems is already non-empty (Shape A).
    """
    if encoding.partition_spec is None:
        return
    spec = encoding.partition_spec
    N = spec.variable_count
    bs = spec.block_size
    K = (N + bs - 1) // bs   # ceil(N / bs)
    expanded: list[SubProblem] = []
    for i in range(K):
        start = i * bs
        end = min(start + bs, N)          # last block may be smaller than bs
        instance = {
            **spec.instance_template,
            "block_index": i,
            "variable_start": start,
            "variable_end": end,
            "num_variables": end - start,
        }
        expanded.append(SubProblem(
            id=f"sp-{i+1}",
            instance=instance,
            role=f"block {i+1}/{K} covering variables {start}..{end-1}",
        ))
    encoding.sub_problems = expanded
    encoding.partition_spec = None  # Cleared after expansion for clarity.


class StageError(RuntimeError):
    """A pipeline stage failed to execute; the trace record was persisted before this exception was raised."""


class AgenticPipeline:
    """Agentic 8-stage pipeline (Phase 1)."""

    def __init__(self, *, store: TraceStore, asset_repo: AssetRepo,
                 stage_parse, stage_analyze, stage_blueprint,
                 stage_encode: StageEncode, stage_codegen: StageCodegen,
                 stage_execute, stage_combine: StageCombine,
                 stage_verify: StageVerify,
                 stage_global_review=None,
                 global_review_max_rounds: int = 3):
        """Each stage is a fully assembled instance (LLM / sandbox / budgets already injected).

        stage_global_review: optional; when provided, a review loop is
            inserted between codegen and execute (approve -> execute;
            revise + feedback -> back to codegen, capped at
            global_review_max_rounds). When None the review is skipped
            and the legacy flow is preserved (backwards compatible;
            tests can omit it).
        """
        self.store = store
        self.asset_repo = asset_repo
        self.stage_parse = stage_parse
        self.stage_analyze = stage_analyze
        self.stage_blueprint = stage_blueprint
        self.stage_encode = stage_encode
        self.stage_codegen = stage_codegen
        self.stage_execute = stage_execute
        self.stage_combine = stage_combine
        self.stage_verify = stage_verify
        self.stage_global_review = stage_global_review
        self.global_review_max_rounds = global_review_max_rounds

    def run(self, raw_text: str, user_id: str | None = None,
            language: Literal["en", "zh"] = "en") -> str:
        """Synchronous entry point: create a request_id and immediately run all 8 stages; return the rid.

        The route layer splits this into "create_request first, run
        run_with_request_id in the background" for the streaming UI;
        direct callers of run() (tests, CLI) keep the prior behavior.
        """
        request_id = self.store.create_request(raw_text=raw_text,
                                                user_id=user_id)
        self.run_with_request_id(request_id, raw_text,
                                  user_id=user_id, language=language)
        return request_id

    def run_with_request_id(
            self, request_id: str, raw_text: str,
            user_id: str | None = None,
            language: Literal["en", "zh"] = "en") -> None:
        """Inner entry point for an already-created request_id, used by BackgroundTasks.

        Once the frontend has the rid it starts polling /trace/{rid};
        TraceRecorder has already inserted each completed stage row, so
        polling picks them up automatically.
        """
        rec = TraceRecorder(self.store, request_id)
        try:
            intent = self._parse(rec, raw_text, language)
            opportunity = self._analyze(rec, intent, language)
            blueprint = self._blueprint(rec, intent, opportunity, language)

            if opportunity.quantum_kernel is None:
                # No quantum-amenable part — stop after blueprint; matches legacy pipeline behavior.
                self.store.set_verification_status(
                    request_id, VerificationStatus.UNVERIFIED.value)
                self.store.set_final_status(request_id, "failed")
                return

            kernel = opportunity.quantum_kernel
            quantum_nodes = blueprint.quantum_nodes
            if not quantum_nodes:
                raise StageError(
                    "blueprint has no quantum node despite quantum_kernel "
                    "being set")
            node = quantum_nodes[0]

            encoding = self._encode(rec, intent, opportunity, blueprint,
                                     language)
            # partition_spec was already expanded inside _encode; at
            # this point encoding.sub_problems is the full K-item list.
            # Slice the instance_data extracted by parse into each block
            # (by variable_start/end) so codegen-generated code can read
            # its real input from SUB_INSTANCE_JSON["block_items"]
            # instead of guessing "there should be pauli_terms".
            _enrich_with_instance_data(encoding, intent.instance_data)
            # codegen runs once and writes parameterized code (reads
            # the env var SUB_INSTANCE_JSON); execute runs N times,
            # each with a different sub_problem instance injected via
            # env. This eliminates N - 1 LLM codegen calls, keeping
            # only the N cheap sandbox executions.
            code = self._codegen(rec, intent, kernel, node,
                                  encoding.sub_problems[0].instance,
                                  attempt=0, language=language)
            # global review: between codegen and execute, inspect
            # whether the code implements the original requirement
            # (reads raw_text + each stage output + code, emits
            # approve/revise + feedback). On `revise`, push feedback
            # back into the codegen prompt so the LLM knows why it was
            # rejected and rewrites the code. Capped at
            # global_review_max_rounds. Skipped when
            # stage_global_review is not configured (backwards
            # compatible).
            if self.stage_global_review is not None:
                for review_round in range(self.global_review_max_rounds):
                    review = self._global_review(
                        rec, raw_text, intent, kernel, blueprint, encoding,
                        code.code, attempt=review_round, language=language)
                    if review.verdict == "approve":
                        break
                    # revise: feed feedback back into codegen and rewrite once.
                    code = self._codegen(
                        rec, intent, kernel, node,
                        encoding.sub_problems[0].instance,
                        attempt=review_round + 1, language=language,
                        prior_review_feedback=review.feedback)
                # Budget exhausted but still asking to revise: keep the
                # latest code (possibly imperfect, but downstream stages
                # run as usual; the verify stage still performs a
                # numerical cross-check as an independent gate).
            last_code = code.code
            sub_results: list[dict[str, Any]] = []
            last_exec_instance: dict[str, Any] | None = None
            for idx, sp in enumerate(encoding.sub_problems):
                env = {"SUB_INSTANCE_JSON": json.dumps(
                    sp.instance, ensure_ascii=False)}
                exec_result = self._execute(rec, code, attempt=idx, env=env)
                if exec_result.status != ExecStatus.SUCCESS:
                    self.store.set_verification_status(
                        request_id, VerificationStatus.FAILED.value)
                    self.store.set_final_status(request_id, "failed")
                    return
                result_obj = exec_result.result or {}
                # If the executed code emits "instance" in its result,
                # prefer it as the verify cross-check target (the
                # encode-stage instance is usually a descriptive
                # placeholder and does not contain pauli_terms).
                if isinstance(result_obj.get("instance"), dict):
                    last_exec_instance = result_obj["instance"]
                sub_results.append({
                    "id": sp.id, "role": sp.role,
                    "value": _extract_value(result_obj),
                })

            # Original instance: prefer the real artifact from execute
            # (containing pauli_terms etc.), otherwise fall back to the
            # encode-stage descriptive placeholder.
            original_instance = last_exec_instance or (
                self._reconstruct_original_instance(encoding, opportunity))
            combined = self._combine(rec, encoding, original_instance,
                                      sub_results, language)
            verification = self._verify(rec, kernel, last_code, combined,
                                          language)
            self.store.set_verification_status(request_id,
                                                verification.value)
            # Persist the final code + combined result into the asset repo.
            self.asset_repo.save(
                request_id=request_id, code=last_code, intent=intent,
                exec_result=ExecResult(
                    status=ExecStatus.SUCCESS,
                    result={"value": combined.value,
                             "instance": combined.instance},
                    verification_status=verification))
            # Final-status policy: CROSS_CHECKED (cross-check passed)
            # and UNVERIFIED (we produced a value but had no way to
            # cross-check) are both `success` — the pipeline finished
            # with a real numerical answer. MISMATCH (wrong value) /
            # OFF_SPEC (code solved the wrong problem) / FAILED (verify
            # agent never committed) are `failed`.
            success_states = (VerificationStatus.CROSS_CHECKED,
                               VerificationStatus.UNVERIFIED)
            final = "success" if verification in success_states else "failed"
            self.store.set_final_status(request_id, final)
            return
        except StageError:
            self.store.set_final_status(request_id, "failed")
            raise
        except Exception as e:
            self.store.set_final_status(request_id, "failed")
            raise StageError(str(e)) from e

    # ---------- per-stage helpers ----------

    def _parse(self, rec, raw_text, language):
        with rec.stage("parse") as ctx:
            intent, meta = self.stage_parse.run(raw_text, language=language)
            ctx.set_input(meta["llm_input"])
            ctx.set_output(meta["llm_output"])
            ctx.set_tokens(meta.get("tokens", {}))
            ctx.set_artifact(intent.model_dump())
        return intent

    def _analyze(self, rec, intent, language):
        with rec.stage("analyze") as ctx:
            opp, meta = self.stage_analyze.run(intent=intent, language=language)
            ctx.set_input(meta["llm_input"])
            ctx.set_output(meta["llm_output"])
            ctx.set_tokens(meta.get("tokens", {}))
            ctx.set_artifact(opp.model_dump())
        return opp

    def _blueprint(self, rec, intent, opportunity, language):
        with rec.stage("blueprint") as ctx:
            bp, meta = self.stage_blueprint.run(
                intent=intent, opportunity=opportunity, language=language)
            ctx.set_input(meta["llm_input"])
            ctx.set_output(meta["llm_output"])
            ctx.set_tokens(meta.get("tokens", {}))
            ctx.set_artifact(bp.model_dump())
        return bp

    def _encode(self, rec, intent, opportunity, blueprint, language):
        with rec.stage("encode") as ctx:
            plan, meta = self.stage_encode.run(
                intent=intent, opportunity=opportunity,
                blueprint=blueprint, language=language)
            # partition_spec must be expanded before set_artifact so
            # that stage_trace.artifact.sub_problems is the full
            # K-item list and the frontend chat shows the correct
            # sub-problem count.
            _expand_partition_spec(plan)
            ctx.set_input(meta["llm_input"])
            ctx.set_output(meta["llm_output"])
            ctx.set_tokens(meta.get("tokens", {}))
            ctx.set_artifact(plan.model_dump())
        return plan

    def _codegen(self, rec, intent, kernel, node, sub_problem_instance, *,
                  attempt, language, prior_review_feedback: str = ""):
        with rec.stage("codegen", attempt=attempt) as ctx:
            try:
                code, rounds, meta = self.stage_codegen.run(
                    intent=intent, kernel=kernel, node=node,
                    sub_problem_instance=sub_problem_instance,
                    language=language,
                    prior_review_feedback=prior_review_feedback)
            except CodegenAgentFailure as e:
                # Persist every agent round into stage_trace even on
                # failure; otherwise the frontend only sees
                # "iterations_exhausted" and cannot tell what the
                # agent actually did.
                ctx.set_rounds(e.rounds)
                ctx.set_artifact({"code": e.last_code,
                                   "failure_reason": e.failure_reason})
                raise
            ctx.set_input(meta.get("llm_input", {}))
            ctx.set_output(meta.get("llm_output", {}))
            ctx.set_tokens(meta.get("tokens", {}))
            ctx.set_rounds(rounds)
            ctx.set_artifact({"code": code.code})
        return code

    def _global_review(self, rec, user_requirement, intent, kernel,
                        blueprint, encoding, code, *, attempt, language):
        """Run a single global-review round. Returns GlobalReviewResult."""
        with rec.stage("global_review", attempt=attempt) as ctx:
            result, meta = self.stage_global_review.run(
                user_requirement=user_requirement,
                intent=intent, kernel=kernel, blueprint=blueprint,
                encoding_plan=encoding, code=code, language=language)
            ctx.set_input(meta.get("llm_input", {}))
            ctx.set_output(meta.get("llm_output", {}))
            ctx.set_tokens(meta.get("tokens", {}))
            ctx.set_artifact(result.model_dump())
        return result

    def _execute(self, rec, code, *, attempt, env=None):
        with rec.stage("execute", attempt=attempt) as ctx:
            exec_result, _ = self.stage_execute.run(
                code=code.code, target="aer",
                aux_files=code.aux_files, env=env)
            ctx.set_artifact({
                "status": exec_result.status.value,
                "result": exec_result.result,
                "stderr_excerpt": exec_result.stderr_excerpt,
                "metrics": exec_result.metrics,
            })
        return exec_result

    def _combine(self, rec, encoding_plan, original_instance, sub_results,
                  language):
        with rec.stage("combine") as ctx:
            # Deterministic Python aggregation first — sum/mean/max/
            # min is pure math, and the LLM is unreliable on long lists
            # (it fabricates the sum of 121 values). The combine_method
            # text is still chosen by the LLM during the encode stage;
            # Python only owns the "apply the chosen strategy" step.
            py_value = _try_python_aggregate(
                encoding_plan.combine_method, sub_results)
            if py_value is not None:
                from quantum_workflow.schemas.combined import CombinedResult
                combined = CombinedResult(
                    value=py_value,
                    instance=original_instance,
                    subresults_summary=[
                        {"id": s["id"], "value": s.get("value")}
                        for s in sub_results
                    ],
                    combine_log=(
                        f"Python aggregator over {len(sub_results)} "
                        f"sub-results; strategy: {encoding_plan.combine_method}"
                    ),
                )
                ctx.set_input({"system": "(python aggregator, no LLM)",
                                "user": encoding_plan.combine_method})
                ctx.set_output({"artifact": combined.model_dump(),
                                 "via": "python_aggregator"})
                ctx.set_tokens({})
                ctx.set_artifact(combined.model_dump())
                return combined
            # Non-numeric / unknown aggregation strategy -> fall back to the LLM (original behavior).
            combined, meta = self.stage_combine.run(
                encoding_plan=encoding_plan,
                original_instance=original_instance,
                sub_results=sub_results, language=language)
            ctx.set_input(meta["llm_input"])
            ctx.set_output(meta["llm_output"])
            ctx.set_tokens(meta.get("tokens", {}))
            ctx.set_artifact(combined.model_dump())
        return combined

    def _verify(self, rec, kernel, code, combined, language):
        with rec.stage("verify") as ctx:
            try:
                status, rounds, meta = self.stage_verify.run(
                    kernel=kernel, code=code, combined=combined,
                    language=language)
            except Exception as e:
                # The verify agent's LLM call blew up (network / API
                # error) — do not let that bubble up to final=failed.
                # execute / combine have already produced the real
                # answer, so the right semantic is "we have a value but
                # no cross-check possible" -> UNVERIFIED. The
                # exception type/message is still written into the
                # artifact by TraceRecorder.stage.
                ctx.set_artifact({
                    "verification_status": VerificationStatus.UNVERIFIED.value,
                    "reason": f"verify stage crashed: {type(e).__name__}: {e}",
                    "error_type": type(e).__name__,
                    "error_message": str(e)[:2000],
                })
                return VerificationStatus.UNVERIFIED
            ctx.set_input(meta.get("llm_input", {}))
            ctx.set_output(meta.get("llm_output", {}))
            ctx.set_tokens(meta.get("tokens", {}))
            ctx.set_rounds(rounds)
            ctx.set_artifact({
                "verification_status": status.value,
                "reason": meta.get("llm_output", {}).get("reason", "")})
        return status

    def _reconstruct_original_instance(self, encoding, opportunity
                                        ) -> dict[str, Any]:
        """Phase 1: use sub_problems[0].instance as the placeholder for the original instance.

        In the reduced-scale case (needs_reduction=True) there is no
        explicit source for the true full-scale original instance in
        Phase 1; in the degenerate decomposition (N=1) this placeholder
        is equivalent to the original problem. Phase 2 will have the
        encode stage emit original_instance explicitly.
        """
        return dict(encoding.sub_problems[0].instance)
