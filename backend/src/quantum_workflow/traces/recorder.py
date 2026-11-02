# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""
Trace recorder module.

Exposes TraceRecorder.stage(), a context manager pipeline stages use
inside `with` blocks to collect LLM input/output, duration, and
artifact data; on exit the data is persisted to TraceStore
automatically. Trace writes are best-effort — failures are silently
swallowed so they cannot interfere with the main flow.

Agent stages additionally submit an AgentRound list via set_rounds();
on exit the recorder writes them into the agent_round table, foreign-
keyed to the stage_trace row.
"""
import time
from contextlib import contextmanager
from dataclasses import asdict

from .orm import AgentRoundRow, StageTraceRow


def _exception_chain(exc: BaseException) -> str:
    """Walk __cause__ / __context__ recursively and assemble a "TypeA: msgA -> TypeB: msgB" string.

    Used to surface the underlying root cause obscured by an outer SDK
    exception (e.g. an OpenAI APIConnectionError that actually wraps an
    httpx.RemoteProtocolError).
    """
    parts: list[str] = []
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        parts.append(f"{type(cur).__name__}: {cur}")
        cur = cur.__cause__ or cur.__context__
    return " -> ".join(parts)
from .store import TraceStore


def _serialize_round_field(items):
    """Serialize a [ToolCall|ToolResult] list into a JSON-friendly list[dict]."""
    out = []
    for it in items or []:
        try:
            out.append(asdict(it))
        except TypeError:
            # Non-dataclass fallback: convert via __dict__ or keep as-is.
            out.append(getattr(it, "__dict__", it))
    return out


class _Ctx:
    """Mutable container the stage fills with trace data; flushed to the database by the recorder on context exit."""

    def __init__(self):
        self.data: dict = {}

    def set_input(self, v): self.data["llm_input"] = v
    def set_output(self, v): self.data["llm_output"] = v
    def set_artifact(self, v): self.data["artifact"] = v
    def set_tokens(self, v): self.data["token_usage"] = v
    def set_rounds(self, v): self.data["rounds"] = v


class TraceRecorder:
    """Records per-stage traces for a single request.

    Each `with` block corresponds to one pipeline stage; on exit the
    collected data is written into the stage_trace table.
    """

    def __init__(self, store: TraceStore, request_id: str):
        """Initialize the trace recorder.

        Args:
            store: Trace-data persistence store.
            request_id: Unique identifier for the current request; all
                trace rows are linked to this ID.
        """
        self.store = store
        self.request_id = request_id

    @contextmanager
    def stage(self, name: str, attempt: int = 0,
              llm_model: str | None = None):
        """Unified per-stage trace context for the generative pipeline; writes one stage_trace row on exit.

        Args:
            name: Stage name (parse / solution / workflow / codegen / execute).
            attempt: Repair-loop round number, 0-indexed; non-loop
                stages always pass 0.
            llm_model: Optional model identifier.

        If the yield block raises, the exception type + message is
        recorded in stage_trace.artifact.error so the failure remains
        observable (the frontend inspector also sees it); the exception
        is then re-raised unchanged.
        """
        ctx = _Ctx()
        started = time.monotonic()
        caught_exc: BaseException | None = None
        try:
            yield ctx
        except BaseException as e:  # noqa: BLE001 - log then re-raise
            caught_exc = e
            raise
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
            artifact = ctx.data.get("artifact")
            if caught_exc is not None:
                # Write exception summary + cause chain into artifact
                # so the frontend / SQL queries can see the real root
                # cause (e.g. when the SDK wraps httpx.RemoteProtocolError
                # into an OpenAI APIConnectionError "Connection error.",
                # the cause chain reveals the key signal "Server
                # disconnected without sending a response.").
                err_payload = {
                    "error_type": type(caught_exc).__name__,
                    "error_message": str(caught_exc)[:2000],
                    "error_chain": _exception_chain(caught_exc)[:4000],
                }
                artifact = {**(artifact or {}), **err_payload}
            row = StageTraceRow(
                request_id=self.request_id,
                stage=name,
                attempt=attempt,
                llm_input=ctx.data.get("llm_input"),
                llm_output=ctx.data.get("llm_output"),
                llm_model=llm_model,
                duration_ms=duration_ms,
                token_usage=ctx.data.get("token_usage"),
                artifact=artifact,
            )
            try:
                stage_id = self.store.insert_stage_trace(row)
                # If this is an agent stage, also persist the agent_round subtable (best-effort).
                for r in ctx.data.get("rounds", []) or []:
                    self.store.insert_agent_round(AgentRoundRow(
                        stage_trace_id=stage_id,
                        round_number=r.round_number,
                        thought=r.thought,
                        tool_calls=_serialize_round_field(r.tool_calls),
                        tool_results=_serialize_round_field(r.tool_results),
                        duration_ms=r.duration_ms,
                        token_usage=r.token_usage,
                    ))
            except Exception:
                # A trace-write failure must not mask the business exception; stay silent best-effort.
                pass
