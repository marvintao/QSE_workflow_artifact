# QPipe 

QPipe is a quantum workflow that turns a natural-language description of a quantum-computing
need into a real, verified result. The LLM autonomously picks the algorithm,
decomposes the problem into a hybrid classical + quantum DAG, writes Qiskit
code, runs it in a sandbox, and cross-checks the output against a classical
solver.

## Key ideas

- **Generative, not catalogued** — the LLM uses its own quantum knowledge to
  choose the algorithm and the kernels worth solving on a quantum computer.
  There is no preset algorithm catalogue and no hard-coded templates.
- **Hybrid workflow** — most of a real request is classical; only a small
  kernel benefits from quantum. The system generates executable code only for
  those kernels.
- **True agents** — the critical stages (codegen, verify) are tool-using
  agents that converge through their own LLM ↔ tool loop, not one-shot
  generation.
- **Honesty first** — when scale exceeds the budget it shrinks to a feasible
  sub-problem and says so; when nothing is quantum-solvable it stops honestly;
  a two-gate verification blocks "solved the wrong problem but reported
  success".

## Stack

- **Backend** — Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0,
  Qiskit 2.x / qiskit-aer, Jinja2
- **LLM** — Claude (API key or subscription OAuth), Kimi, SiliconFlow, Zhipu,
  AWS Bedrock; each pipeline stage picks its own provider+model
- **Frontend** — React 18, TypeScript, Vite, Tailwind CSS, @xyflow/react
- **Data** — SQLite, two-level tracing (`stage_trace` + `agent_round`)

## Quick start

```bash
# Backend (from backend/)
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp config.example config          # then add your provider + API key
.venv/bin/uvicorn quantum_workflow.api.main:app_factory --factory --port 8000

# Frontend (from frontend/)
npm install
npm run dev                        # http://localhost:5173, proxies /api → :8000
```

Start the backend from `backend/` so the relative paths in `config`
(`./traces.db`, `./assets/store`) resolve correctly. See `backend/config.example`
for all options (provider keys, per-stage models, sandbox/agent budgets).

## How it works

An eight-stage agentic pipeline (with an optional cross-stage review loop):

```
parse → analyze → blueprint → encode → codegen* → [global_review] → execute (×N) → combine → verify*
* = true tool-using agent
```

`parse` structures the request → `analyze` finds the quantum kernels and picks
the algorithm → `blueprint` lays out the classical/quantum DAG → `encode`
splits the full problem into within-budget sub-problems → `codegen` writes and
sandbox-tests kernel code → `execute` runs it → `combine` aggregates the
sub-results → `verify` applies a two-gate verdict (spec alignment + classical
cross-check). The optional `global_review` checks that the generated code
actually solves the user's requirement and bounces back to codegen if not.

## Layout

```
backend/      Python + FastAPI: pipeline, LLM adapters, sandbox, traces, tests
frontend/     React + TS + Vite: three-pane chat / workflow / detail UI
docs/         Design specs and implementation plans
empirical_study/  Study scripts, processed data, figures (see its README)
use_cases/        Benchmark instances + generated NL requirements (see its README)
reports/          Experiment trace DBs and per-run reports
```

## Tests

```bash
cd backend  && .venv/bin/pytest tests/unit -q
cd frontend && npm test -- --run
```
