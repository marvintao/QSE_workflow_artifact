"""
Sandbox executor module.

Runs quantum-circuit Python code as a subprocess in an isolated temp
directory, with process-level isolation via rlimit (RLIMIT_AS,
RLIMIT_CPU) and subprocess timeouts.

Note: rlimit-based isolation is process-level only; real strong
isolation requires Docker containers, which v2 will introduce. v1
relies on the Stage-4 "fill-only" design to limit the LLM's ability to
call system / network APIs.
"""
import json
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


class SandboxExecutor:
    """Run untrusted code inside a restricted subprocess with process-level resource isolation.

    NOTE: rlimit-based sandboxing is process-level only; for true
    isolation v2 should wrap in Docker. v1 trusts the LLM not to call
    os.system / network APIs (constrained by the Stage-4 fill-only model).
    """

    def __init__(self, workdir: Path, timeout_s: int,
                 max_memory_mb: int, max_qubits: int):
        """Initialize the sandbox executor.

        Args:
            workdir: Parent directory for all run directories; each run
                creates its own temp subdirectory here.
            timeout_s: Max wall-clock time in seconds for the
                subprocess; on timeout, return `resource_limit` status.
            max_memory_mb: Subprocess virtual-memory cap in MB,
                enforced via RLIMIT_AS.
            max_qubits: Max qubit count (reserved config field used by
                upper-layer feasibility checks).
        """
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout_s = timeout_s
        self.max_memory_mb = max_memory_mb
        self.max_qubits = max_qubits

    def run(self, code: str,
            aux_files: dict[str, str] | None = None,
            env: dict[str, str] | None = None) -> dict:
        """Write code and aux files into a temp directory, execute, and clean up regardless of outcome.

        Args:
            code: Python source code string to execute.
            aux_files: Aux-file map (filename -> contents) written into
                the same temp directory so the code can import them.
            env: Extra environment variables to inject into the
                subprocess (merged onto os.environ). Typical use is to
                inject variable instance data such as SUB_INSTANCE_JSON
                via env so one codegen artifact can be reused across
                N different instances.
        Returns:
            Dict with status / result / metrics / stderr_excerpt.
        """
        # Use a fresh temp directory per run to isolate filesystem side effects.
        run_dir = Path(tempfile.mkdtemp(dir=self.workdir, prefix="run_"))
        try:
            for name, content in (aux_files or {}).items():
                (run_dir / name).write_text(content)
            script_path = run_dir / "user_code.py"
            script_path.write_text(code)
            return self._execute_script(script_path, env=env)
        finally:
            # Always remove the temp directory regardless of outcome, to keep disk usage bounded.
            shutil.rmtree(run_dir, ignore_errors=True)

    def _execute_script(self, script_path: Path,
                        env: dict[str, str] | None = None) -> dict:
        """Execute the script in a subprocess with rlimit constraints; return a normalized result dict.

        Args:
            script_path: Absolute path to the script to execute.
        Returns:
            Dict with status (success / runtime_error / resource_limit),
            result, metrics, and stderr_excerpt.
        """
        mem_bytes = self.max_memory_mb * 1024 * 1024

        def _preexec():
            # RLIMIT_AS is unavailable or too restrictive on macOS
            # (virtual-address-space accounting differs there); silently
            # skip if it fails.
            try:
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            except (ValueError, resource.error):
                pass
            # RLIMIT_CPU caps cumulative CPU time (sum across all
            # threads), not wall clock. With numpy/BLAS multi-core
            # parallelism, 1s wall = N cores * 1s CPU, so
            # RLIMIT_CPU = timeout_s + 5 would SIGXCPU-kill the process
            # long before wall clock reaches timeout_s. Give a
            # cpu_count multiplier so the wall-clock subprocess.timeout
            # is the actual kill switch.
            import os as _os
            cpu_count = _os.cpu_count() or 1
            cpu_limit = (self.timeout_s + 5) * max(cpu_count, 1)
            try:
                resource.setrlimit(resource.RLIMIT_CPU,
                                   (cpu_limit, cpu_limit))
            except (ValueError, resource.error):
                pass

        # Merge parent environ with caller-supplied env (caller wins on conflict).
        import os as _os
        proc_env = {**_os.environ, **(env or {})}

        started = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True, text=True,
                timeout=self.timeout_s,
                env=proc_env,
                # Windows does not support preexec_fn; apply rlimit only on Unix-like systems.
                preexec_fn=_preexec if sys.platform != "win32" else None,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "resource_limit",
                "result": None,
                "metrics": {"wall_time_s": time.monotonic() - started},
                "stderr_excerpt": "timeout exceeded",
            }
        wall = time.monotonic() - started

        if proc.returncode != 0:
            # Negative returncode = killed by a signal
            # (SIGKILL/SIGXCPU/SIGSEGV) — typically rlimit_cpu /
            # rlimit_as or OS OOM kill. A regular Python exception
            # yields returncode 1 (or whatever positive sys.exit(n)
            # passes). Map this explicitly to `resource_limit` and
            # explain it in stderr so the codegen agent realizes "the
            # code blew the resource budget" instead of blindly editing
            # business logic.
            if proc.returncode < 0:
                sig = -proc.returncode
                tail = proc.stderr[-1500:] if proc.stderr else "(empty)"
                return {
                    "status": "resource_limit",
                    "result": None,
                    "metrics": {"wall_time_s": wall},
                    "stderr_excerpt": (
                        f"killed by signal {sig} "
                        f"(likely CPU rlimit / memory rlimit / OOM — "
                        f"the program ran too long or used too much memory). "
                        f"Reduce problem size, avoid O(N^2)/O(2^N) loops, "
                        f"or use smaller block_size. stderr tail: {tail}"
                    ),
                }
            # Keep only the last 2000 bytes of stderr to avoid massive log payloads landing in the database.
            return {
                "status": "runtime_error",
                "result": None,
                "metrics": {"wall_time_s": wall},
                "stderr_excerpt": proc.stderr[-2000:],
            }

        # Convention: the script prints its final result as JSON on the last stdout line.
        # Parse last stdout line as JSON result.
        last_line = (proc.stdout.strip().splitlines()[-1]
                     if proc.stdout.strip() else "{}")
        try:
            result = json.loads(last_line)
        except json.JSONDecodeError:
            # If the last line is not valid JSON, save the full stdout as raw text.
            result = {"raw_stdout": proc.stdout}

        return {
            "status": "success",
            "result": result,
            "metrics": {"wall_time_s": wall},
            "stderr_excerpt": proc.stderr[-2000:] if proc.stderr else None,
        }
