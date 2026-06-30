/**
 * MSW request handlers and test fixtures.
 *
 * Provides two pieces:
 *   1. fakeFullTrace — a mock unified `stages` array covering the eight agentic stages
 *      (parse / analyze / blueprint / encode / codegen / execute / combine / verify),
 *      reusable across component tests.
 *   2. handlers — MSW HTTP interceptors that simulate the backend /api/request and /api/trace endpoints.
 */
import { http, HttpResponse } from "msw";
import type { FullTrace } from "../api/types";

const RID = "test-rid-1";

/** Full-trace fixture (H2 ground-state energy scenario), built on the new six-stage structure. */
export const fakeFullTrace: FullTrace = {
  request: {
    request_id: RID,
    raw_text: "Find H2 ground state",
    final_status: "success",
    verification_status: "cross_checked",
    created_at: "2026-05-22T00:00:00Z",
  },
  stages: [
    {
      id: 1,
      stage: "parse",
      attempt: 0,
      llm_input: { user: "..." },
      llm_output: { domain: "chemistry" },
      llm_model: "claude-opus-4-7",
      duration_ms: 1200,
      token_usage: { input_tokens: 120, output_tokens: 60 },
      artifact: {
        domain: "chemistry",
        problem_statement: "ground state of H2",
        constraints: {},
        data_scale_hints: { qubit_estimate: 2 },
        ambiguities: [],
      },
      created_at: "2026-05-22T00:00:01Z",
    },
    {
      id: 2,
      stage: "analyze",
      attempt: 0,
      llm_input: { user: "..." },
      llm_output: { algorithm: "VQE" },
      llm_model: "claude-opus-4-7",
      duration_ms: 5000,
      token_usage: { input_tokens: 220, output_tokens: 120 },
      artifact: {
        decomposition: [
          { name: "求基态", description: "本征值最小化", disposition: "quantum" },
        ],
        quantum_kernel: {
          algorithm: "VQE",
          algorithm_rationale: "适配本征值最小化",
          subproblem: "H2 哈密顿量基态",
          io_interface: "哈密顿量入,本征值出",
          full_scale_qubits: 2,
          feasible_qubits: 24,
          needs_reduction: false,
          reduced_qubits: 2,
          reduction_note: "",
        },
        no_quantum_reason: null,
      },
      created_at: "2026-05-22T00:00:02Z",
    },
    {
      id: 3,
      stage: "blueprint",
      attempt: 0,
      llm_input: { user: "..." },
      llm_output: { nodes: 3 },
      llm_model: "claude-opus-4-7",
      duration_ms: 6000,
      token_usage: { input_tokens: 330, output_tokens: 200 },
      artifact: {
        nodes: [
          {
            id: "c1",
            name: "构造哈密顿量",
            kind: "classical",
            description: "从已验证积木库取 H2 哈密顿量",
            inputs: ["分子标识"],
            outputs: ["hamiltonian"],
          },
          {
            id: "q1",
            name: "VQE 内核",
            kind: "quantum",
            description: "参数化 ansatz + estimator 求最低本征值",
            inputs: ["hamiltonian"],
            outputs: ["ground_state_energy"],
          },
          {
            id: "c2",
            name: "结果汇报",
            kind: "classical",
            description: "整理输出",
            inputs: ["ground_state_energy"],
            outputs: ["report"],
          },
        ],
        edges: [
          { from_id: "c1", to_id: "q1" },
          { from_id: "q1", to_id: "c2" },
        ],
        feasibility: { qubit_count: 2, estimated_depth: 12, passes_limits: true },
      },
      created_at: "2026-05-22T00:00:03Z",
    },
    {
      id: 35,
      stage: "encode",
      attempt: 0,
      llm_input: { user: "..." },
      llm_output: { strategy: "退化(N=1)" },
      llm_model: "claude-opus-4-7",
      duration_ms: 1500,
      token_usage: { input_tokens: 380, output_tokens: 150 },
      artifact: {
        strategy: "退化(N=1)",
        strategy_rationale: "H2 全规模 2 量子比特已在预算内,无需分解",
        sub_problems: [
          {
            id: "sp-1",
            instance: { type: "hamiltonian", pauli_terms: [] },
            role: "H2 完整哈密顿量",
          },
        ],
        combine_method: "直接采用 sp-1 的本征值",
      },
      created_at: "2026-05-22T00:00:0Z",
    },
    {
      id: 4,
      stage: "codegen",
      attempt: 0,
      llm_input: { user: "..." },
      llm_output: { code: "..." },
      llm_model: "claude-opus-4-7",
      duration_ms: 8000,
      token_usage: { input_tokens: 440, output_tokens: 300 },
      artifact: {
        code: 'import json\n\ndef main():\n    return {"value": -1.137, "instance": {"type": "hamiltonian", "pauli_terms": []}}\n',
      },
      created_at: "2026-05-22T00:00:04Z",
    },
    {
      id: 5,
      stage: "execute",
      attempt: 0,
      llm_input: null,
      llm_output: null,
      llm_model: null,
      duration_ms: 800,
      token_usage: null,
      artifact: {
        status: "success",
        result: {
          value: -1.137,
          instance: { type: "hamiltonian", pauli_terms: [] },
        },
        stderr_excerpt: null,
        metrics: { wall_time_s: 0.8 },
      },
      created_at: "2026-05-22T00:00:05Z",
    },
    {
      id: 55,
      stage: "combine",
      attempt: 0,
      llm_input: { user: "..." },
      llm_output: { value: -1.137 },
      llm_model: "claude-opus-4-7",
      duration_ms: 900,
      token_usage: { input_tokens: 220, output_tokens: 90 },
      artifact: {
        value: -1.137,
        instance: { type: "hamiltonian", pauli_terms: [] },
        subresults_summary: [{ id: "sp-1", value: -1.137 }],
        combine_log: "退化分解,直接采用 sp-1 结果",
      },
      created_at: "2026-05-22T00:00:055Z",
    },
    {
      id: 6,
      stage: "verify",
      attempt: 0,
      llm_input: { user: "..." },
      llm_output: { verdict: { aligned: true, reason: "VQE 内核已正确实现" } },
      llm_model: "claude-opus-4-7",
      duration_ms: 1200,
      token_usage: { input_tokens: 100, output_tokens: 30 },
      artifact: {
        verification_status: "cross_checked",
        reason: "VQE 内核已正确实现,数值与经典精确对角化一致",
      },
      created_at: "2026-05-22T00:00:06Z",
    },
  ],
};

/** MSW handler list. */
export const handlers = [
  http.post("/api/request", async ({ request }) => {
    const body = (await request.json()) as { raw_text: string };
    if (body.raw_text === "FAIL") {
      return HttpResponse.json(
        { detail: "pipeline failed: simulated" },
        { status: 502 },
      );
    }
    return HttpResponse.json({ request_id: RID });
  }),
  http.get("/api/request/:id", ({ params }) => {
    if (params.id === "missing") {
      return HttpResponse.json({ detail: "request not found" }, { status: 404 });
    }
    return HttpResponse.json(fakeFullTrace.request);
  }),
  http.get("/api/trace/:id", ({ params }) => {
    if (params.id === "missing") {
      return HttpResponse.json({ detail: "request not found" }, { status: 404 });
    }
    return HttpResponse.json(fakeFullTrace);
  }),
];
