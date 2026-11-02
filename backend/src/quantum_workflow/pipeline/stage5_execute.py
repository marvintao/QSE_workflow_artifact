# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""
Pipeline stage 5: execute.

Input: a generated quantum-circuit Python code string + aux files.
Output: ExecResult (status, result data, runtime metrics, stderr excerpt).

Submits the code to the sandbox executor and converts the raw dict
result into a strongly typed ExecResult. v1 only supports the local
Aer simulator backend; hardware backends (IBM) arrive in v1.1.
"""
from quantum_workflow.schemas.exec import ExecResult, ExecStatus


class Stage5Execute:
    """Stage 5: execute generated quantum-circuit code in the sandbox and collect a structured result."""

    def __init__(self, sandbox):
        """Initialize the execute stage.

        Args:
            sandbox: Sandbox executor that must implement run(code, aux_files).
        """
        self.sandbox = sandbox

    def run(self, *, code: str, target: str = "aer",
            aux_files: dict[str, str] | None = None,
            env: dict[str, str] | None = None) -> tuple[ExecResult, dict]:
        """Execute code on the chosen backend and return a structured result with metadata.

        Args:
            code: Python source code string to execute.
            target: Execution backend; currently only "aer" (local simulator) is supported.
            aux_files: Runtime aux-file map (filename -> contents); may be empty.
            env: Extra environment variables to inject (typically
                SUB_INSTANCE_JSON, so one code body runs N times across
                different sub_problems).
        Returns:
            (ExecResult, meta_dict), where meta_dict contains the target field.
        """
        # v1 only supports the local Aer backend; reject any other target up front with a clear error.
        if target != "aer":
            raise NotImplementedError(
                "v1 only supports 'aer'; 'ibm' coming in v1.1")
        raw = self.sandbox.run(code, aux_files=aux_files or {}, env=env)
        # Convert the sandbox's raw dict into a strongly typed object so callers can handle it uniformly.
        result = ExecResult(
            status=ExecStatus(raw["status"]),
            result=raw.get("result"),
            metrics=raw.get("metrics", {}),
            stderr_excerpt=raw.get("stderr_excerpt"),
        )
        return result, {"target": target}
