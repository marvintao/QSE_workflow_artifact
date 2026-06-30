"""
SQLAlchemy ORM models for trace data.

Defines three tables:
  - RequestRow: one row per pipeline invocation (top-level request).
  - StageTraceRow: unified per-stage trace records for the generative pipeline.
  - AgentRoundRow: one row per agent iteration (LLM thought + tool
    calls + tool results) for agent stages (codegen / verify).
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return the current UTC time; used as the default factory for created_at columns."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Common DeclarativeBase for every ORM-mapped class."""
    pass


class RequestRow(Base):
    """Top-level request record; one row per pipeline invocation."""

    __tablename__ = "request"
    request_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # final_status is updated by TraceStore.set_final_status when the pipeline finishes (success/failed).
    final_status: Mapped[str | None] = mapped_column(String, nullable=True)
    # verification_status is written by the generative pipeline after execution + classical cross-check.
    verification_status: Mapped[str | None] = mapped_column(String, nullable=True)


class StageTraceRow(Base):
    """Unified per-stage trace table for the generative pipeline.

    One row per pipeline stage (parse / solution / workflow / codegen
    / execute). When a self-repair loop causes the same stage to run
    multiple times, the attempt field (0-indexed) distinguishes the
    rounds. Each stage's concrete artifact is stored uniformly in
    `artifact` (JSON) to keep the schema generic.
    """

    __tablename__ = "stage_trace"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String, ForeignKey("request.request_id"))
    stage: Mapped[str] = mapped_column(String)            # stage name
    attempt: Mapped[int] = mapped_column(Integer, default=0)  # repair-loop round number
    llm_input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # artifact stores the stage's structured output (semantics differ per stage; uniformly carried as JSON).
    artifact: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AgentRoundRow(Base):
    """Trace record for one agent iteration (LLM thought + tool calls + tool results).

    Only agent-driven stages (codegen / verify) write to this table;
    other stages stay confined to stage_trace. A single stage_trace
    row can be associated with multiple agent_round rows, ordered by
    round_number ascending.
    """

    __tablename__ = "agent_round"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage_trace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stage_trace.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)  # 0-indexed
    thought: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tool_results: Mapped[list | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
