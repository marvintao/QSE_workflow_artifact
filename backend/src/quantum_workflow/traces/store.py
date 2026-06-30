"""
Trace-data persistence module.

TraceStore wraps a SQLAlchemy engine and exposes read/write APIs for
the request and stage_trace tables. It creates tables on init (if they
do not exist yet) and supports any SQLAlchemy-compatible database URL.
"""
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .orm import AgentRoundRow, Base, RequestRow, StageTraceRow


class TraceStore:
    """Persistence layer for trace data; encapsulates session management and table I/O."""

    def __init__(self, db_url: str):
        """Initialize the store: connect to the database and create all trace tables (idempotent).

        Args:
            db_url: SQLAlchemy connection string, e.g.
                "sqlite:///traces.db".
        """
        self.engine = create_engine(db_url, future=True)
        # create_all is idempotent: skips existing tables without overwriting their data.
        Base.metadata.create_all(self.engine)

    def create_request(self, raw_text: str, user_id: str | None = None) -> str:
        """Create a new request record and return the auto-generated UUID request_id.

        Args:
            raw_text: Raw user input text.
            user_id: Optional user identifier.
        Returns:
            The new request_id string.
        """
        rid = str(uuid.uuid4())
        with Session(self.engine) as s:
            s.add(RequestRow(request_id=rid, raw_text=raw_text, user_id=user_id))
            s.commit()
        return rid

    def set_final_status(self, request_id: str, status: str) -> None:
        """Update the request's final status ("success" or "failed").

        Args:
            request_id: Target request ID.
            status: Final status string.
        Raises:
            ValueError: When the request_id does not exist in the database.
        """
        with Session(self.engine) as s:
            req = s.get(RequestRow, request_id)
            if req is None:
                raise ValueError(f"request_id {request_id!r} not found")
            req.final_status = status
            s.commit()

    def set_verification_status(self, request_id: str, status: str) -> None:
        """Update the request's verification status (cross_checked / unverified / mismatch / off_spec / failed).

        Args:
            request_id: Target request ID.
            status: Verification status string.
        Raises:
            ValueError: When the request_id does not exist.
        """
        with Session(self.engine) as s:
            req = s.get(RequestRow, request_id)
            if req is None:
                raise ValueError(f"request_id {request_id!r} not found")
            req.verification_status = status
            s.commit()

    def get_request(self, request_id: str) -> RequestRow | None:
        """Look up a request record by primary key; return None when missing."""
        with Session(self.engine) as s:
            return s.get(RequestRow, request_id)

    def insert_stage_trace(self, row: StageTraceRow) -> int:
        """Insert a unified stage-trace record; return the new row id (used to associate agent_round rows)."""
        with Session(self.engine) as s:
            s.add(row)
            s.commit()
            return row.id

    def list_stage_traces(self, request_id: str) -> list[StageTraceRow]:
        """Return every stage-trace row for the given request, ordered by insertion (id ascending)."""
        with Session(self.engine) as s:
            return list(s.scalars(
                select(StageTraceRow)
                .where(StageTraceRow.request_id == request_id)
                .order_by(StageTraceRow.id)
            ).all())

    def insert_agent_round(self, row: AgentRoundRow) -> int:
        """Insert one agent-round record; return the new row id."""
        with Session(self.engine) as s:
            s.add(row)
            s.commit()
            return row.id

    def list_agent_rounds(self, stage_trace_id: int) -> list[AgentRoundRow]:
        """Return every agent round for the given stage_trace_id, ordered by round_number ascending."""
        with Session(self.engine) as s:
            return list(s.scalars(
                select(AgentRoundRow)
                .where(AgentRoundRow.stage_trace_id == stage_trace_id)
                .order_by(AgentRoundRow.round_number)
            ).all())
