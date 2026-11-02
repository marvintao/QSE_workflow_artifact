# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""API route definitions.

Exposes three endpoints: submit request, query request, and fetch the
full trace. Traces are returned using the unified stage_trace structure.
"""
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from quantum_workflow.pipeline.agentic_orchestrator import StageError
from quantum_workflow.traces.store import TraceStore


def _run_pipeline_safely(pipeline, request_id: str, raw_text: str,
                          user_id: str | None, language: str) -> None:
    """Background-task wrapper. The pipeline already sets
    final_status='failed' internally on error; this wrapper additionally
    dumps the exception to stderr (for uvicorn log inspection) instead of
    silently swallowing it."""
    import sys
    import traceback
    try:
        pipeline.run_with_request_id(
            request_id, raw_text, user_id=user_id, language=language)
    except Exception:
        # Do not re-raise (this is a background task), but the full
        # traceback must remain visible — otherwise the only evidence
        # left of a failure would be final=failed.
        print(f"[pipeline] request {request_id} failed:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


class RequestPayload(BaseModel):
    """Request body for submitting a quantum-workflow request.

    Fields:
        raw_text: Raw user requirement text, length 1-1_000_000.
        user_id: Optional user identifier for attribution.
        language: Language code (en/zh).

    Model selection is fully driven by backend/config (each stage uses
    `<stage>_agent`, empty falls back to the global LLM_PROVIDER). The
    request body does not accept model overrides — switching models means
    editing config and restarting.
    """

    raw_text: str = Field(..., min_length=1, max_length=1_000_000)
    user_id: str | None = None
    language: Literal["en", "zh"] = "en"


def make_router(pipeline, store: TraceStore) -> APIRouter:
    """Build and return an APIRouter exposing all API endpoints.

    Args:
        pipeline: The global pipeline built at startup (shared by all requests).
        store: Trace-record store instance.
    """
    router = APIRouter()

    @router.post("/request")
    def create_request(payload: RequestPayload,
                        background_tasks: BackgroundTasks):
        """Submit a request: immediately create the rid, return it, and
        run the pipeline in the background.

        Once the frontend has the rid it begins polling /trace/{rid};
        each completed stage is persisted by TraceRecorder, so polling
        observes progress. A pipeline failure writes
        final_status='failed' + verification_status='failed', so the
        frontend stops polling once it sees a terminal state.
        """
        rid = store.create_request(raw_text=payload.raw_text,
                                    user_id=payload.user_id)
        background_tasks.add_task(
            _run_pipeline_safely, pipeline, rid,
            payload.raw_text, payload.user_id, payload.language)
        return {"request_id": rid}

    @router.get("/request/{request_id}")
    def get_request(request_id: str):
        """Return basic status information for the given request."""
        req = store.get_request(request_id)
        if req is None:
            raise HTTPException(status_code=404, detail="request not found")
        return {
            "request_id": req.request_id,
            "raw_text": req.raw_text,
            "final_status": req.final_status,
            "verification_status": req.verification_status,
            "created_at": req.created_at.isoformat(),
        }

    @router.get("/trace/{request_id}")
    def get_trace(request_id: str):
        """Return the full execution trace for a request (unified stage_trace structure plus optional agent_round entries)."""
        req = store.get_request(request_id)
        if req is None:
            raise HTTPException(status_code=404, detail="request not found")
        stages = store.list_stage_traces(request_id)
        stages_payload = []
        for s in stages:
            rounds = store.list_agent_rounds(s.id)
            stages_payload.append(_serialize_stage(s, agent_rounds=rounds))
        return {
            "request": {
                "request_id": req.request_id,
                "raw_text": req.raw_text,
                "final_status": req.final_status,
                "verification_status": req.verification_status,
                "created_at": req.created_at.isoformat(),
            },
            "stages": stages_payload,
        }

    return router


def _serialize_stage(s, agent_rounds=None):
    """Serialize a stage_trace row into a JSON-friendly dict, optionally including a list of agent rounds."""
    out = {"id": s.id, "stage": s.stage, "attempt": s.attempt,
           "llm_input": s.llm_input, "llm_output": s.llm_output,
           "llm_model": s.llm_model, "duration_ms": s.duration_ms,
           "token_usage": s.token_usage, "artifact": s.artifact,
           "created_at": s.created_at.isoformat()}
    if agent_rounds:
        out["rounds"] = [{
            "round_number": r.round_number,
            "thought": r.thought,
            "tool_calls": r.tool_calls,
            "tool_results": r.tool_results,
            "duration_ms": r.duration_ms,
            "token_usage": r.token_usage,
            "created_at": r.created_at.isoformat(),
        } for r in agent_rounds]
    return out
