"""Dependency-injection factory module.

Builds AgenticPipeline + TraceStore from a Settings instance. Each
stage's LLM is resolved by build_llm_for_stage from the `<stage>_agent`
per-stage override (empty falls back to the global LLM_PROVIDER) — model
selection is fully config-driven, with no per-request override.

Environment toggles (for ablation experiments, not in the config file):
- `SKIP_GLOBAL_REVIEW=1`: skip the global_review stage (codegen runs
  straight into execute with no reviewer round-trip).
"""
import os
from pathlib import Path

from quantum_workflow.assets.null_repo import NullAssetRepo
from quantum_workflow.config import Settings
from quantum_workflow.llm.factory import build_llm_for_stage
from quantum_workflow.pipeline.agentic_orchestrator import AgenticPipeline
from quantum_workflow.pipeline.stage1_parse import Stage1Parse
from quantum_workflow.pipeline.stage2_analyze import Stage2Analyze
from quantum_workflow.pipeline.stage3_blueprint import Stage3Blueprint
from quantum_workflow.pipeline.stage5_execute import Stage5Execute
from quantum_workflow.pipeline.stage_codegen import StageCodegen
from quantum_workflow.pipeline.stage_combine import StageCombine
from quantum_workflow.pipeline.stage_encode import StageEncode
from quantum_workflow.pipeline.stage_global_review import StageGlobalReview
from quantum_workflow.pipeline.stage_verify import StageVerify
from quantum_workflow.sandbox.executor import SandboxExecutor
from quantum_workflow.traces.store import TraceStore


def build_pipeline_from_settings(
        settings: Settings,
) -> tuple[AgenticPipeline, TraceStore]:
    """Build an AgenticPipeline and its backing TraceStore.

    Each stage reads `<stage>_agent=<provider>:<model>` from config, with
    an empty value falling back to the global `LLM_PROVIDER`/`LLM_MODEL`
    etc. Switching models means editing config and restarting; runtime
    overrides are not supported.
    """
    store = TraceStore(f"sqlite:///{settings.trace_db_path}")
    asset_repo = NullAssetRepo(root=Path(settings.assets_dir))

    sandbox = SandboxExecutor(
        workdir=Path(settings.assets_dir) / "_sandbox",
        timeout_s=settings.sandbox_timeout_s,
        max_memory_mb=settings.sandbox_memory_mb,
        max_qubits=settings.sandbox_max_qubits,
    )

    llm_parse = build_llm_for_stage(settings, "parse")
    llm_analyze = build_llm_for_stage(settings, "analyze")
    llm_blueprint = build_llm_for_stage(settings, "blueprint")
    llm_encode = build_llm_for_stage(settings, "encode")
    llm_codegen = build_llm_for_stage(settings, "codegen")
    llm_combine = build_llm_for_stage(settings, "combine")
    llm_verify = build_llm_for_stage(settings, "verify")
    # global_review: use a configured global_review_agent if present,
    # otherwise reuse the verify_agent LLM (similar role — both inspect
    # an output; verify judges numerical results, global_review judges code).
    llm_global_review = (
        build_llm_for_stage(settings, "global_review")
        if settings.global_review_agent else llm_verify
    )

    pipeline = AgenticPipeline(
        store=store, asset_repo=asset_repo,
        stage_parse=Stage1Parse(llm=llm_parse, model_name=llm_parse.model),
        stage_analyze=Stage2Analyze(
            llm=llm_analyze, model_name=llm_analyze.model,
            feasible_qubits=settings.sandbox_max_qubits),
        stage_blueprint=Stage3Blueprint(
            llm=llm_blueprint, model_name=llm_blueprint.model),
        stage_encode=StageEncode(
            llm=llm_encode, model_name=llm_encode.model),
        stage_codegen=StageCodegen(
            llm=llm_codegen, model_name=llm_codegen.model, sandbox=sandbox,
            max_iterations=settings.codegen_max_iterations,
            max_tool_calls=settings.codegen_max_tool_calls,
            max_tokens=settings.codegen_max_tokens),
        stage_global_review=(
            None if os.environ.get("SKIP_GLOBAL_REVIEW") == "1"
            else StageGlobalReview(
                llm=llm_global_review, model_name=llm_global_review.model)),
        stage_execute=Stage5Execute(sandbox=sandbox),
        stage_combine=StageCombine(
            llm=llm_combine, model_name=llm_combine.model),
        stage_verify=StageVerify(
            llm=llm_verify, model_name=llm_verify.model,
            max_iterations=settings.verify_max_iterations,
            max_tool_calls=settings.verify_max_tool_calls,
            max_tokens=settings.verify_max_tokens),
        global_review_max_rounds=settings.global_review_max_rounds,
    )
    return pipeline, store
