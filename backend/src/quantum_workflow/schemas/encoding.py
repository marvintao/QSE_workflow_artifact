"""Encoding-stage data models: decompose the full-scale problem into sub-problems that fit the feasible budget."""

from pydantic import BaseModel, Field, model_validator


class SubProblem(BaseModel):
    """A single decomposed sub-problem."""

    id: str                       # unique sub-problem id, used to correlate during combine
    instance: dict                # same schema as ExecArtifact.result.instance
                                  # (e.g. {"type": "hamiltonian"|"qubo", ...})
    role: str                     # free-form description of this sub-problem's role in the original problem


class PartitionSpec(BaseModel):
    """Partitioning rule: at the orchestrator layer Python expands this
    into K SubProblems so the LLM does not have to enumerate, say, 81
    sub_problems by hand (which risks oversized JSON output or the LLM
    abbreviating with `...` and breaking parsing)."""

    variable_count: int = Field(..., gt=0)     # full-scale variable / qubit count N
    block_size: int = Field(..., gt=0)         # max variables per block (<= feasible_qubits)
    instance_template: dict = Field(default_factory=dict)
    # ^ Per-block shared, invariant structure (type / algorithm hints /
    #   global parameters); Python injects block_index / variable_start /
    #   variable_end / num_variables into each block's instance.


class EncodingPlan(BaseModel):
    """Output of stage 4 (encode): decomposition strategy + sub-problem list + combine plan.

    The LLM produces exactly one of the following:
    - **Small scale** (N <= feasible_qubits, or degenerate): list
      `sub_problems` directly (typically 1 entry).
    - **Large scale** (needs_reduction=true): emit a `partition_spec`
      metadata block and leave `sub_problems` as `[]`; the orchestrator
      expands it.
    """

    strategy: str                                # decomposition strategy chosen by the LLM
    strategy_rationale: str                      # why this strategy was chosen
    sub_problems: list[SubProblem] = Field(default_factory=list)
    partition_spec: PartitionSpec | None = None
    combine_method: str                          # combine-method description handed to the combine stage

    @model_validator(mode="after")
    def _exactly_one_decomposition_form(self) -> "EncodingPlan":
        """Exactly one of non-empty sub_problems or non-null partition_spec must be set."""
        has_subs = len(self.sub_problems) > 0
        has_spec = self.partition_spec is not None
        if has_subs == has_spec:
            raise ValueError(
                "EncodingPlan must have EXACTLY ONE of "
                "sub_problems (non-empty) or partition_spec (non-null), "
                f"got sub_problems={len(self.sub_problems)}, "
                f"partition_spec={'set' if has_spec else 'null'}")
        return self
