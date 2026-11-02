// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * Backend API data-type definitions.
 * Covers the five generative pipeline stages
 * (parse -> quantum-opportunity analyze -> hybrid blueprint -> codegen -> execute)
 * plus the additional verify trace.
 */

import type { Lang } from "../i18n/types";

/** Structured user intent produced by LLM parsing. */
export interface ParsedIntent {
  domain: string;
  problem_statement: string;
  constraints: Record<string, string>;
  data_scale_hints: Record<string, number>;
  ambiguities: string[];
}

/** Quantum-opportunity analysis: a single sub-task obtained from problem decomposition. */
export interface SubTask {
  name: string;
  description: string;
  disposition: "classical" | "quantum";
}

/** Quantum-opportunity analysis: the quantum kernel spec identified by the LLM. */
export interface QuantumKernel {
  algorithm: string;
  algorithm_rationale: string;
  subproblem: string;
  io_interface: string;
  full_scale_qubits: number;
  feasible_qubits: number;
  needs_reduction: boolean;
  reduced_qubits: number;
  reduction_note: string;
}

/** Artifact of stage 2 (quantum-opportunity analyze). */
export interface QuantumOpportunity {
  decomposition: SubTask[];
  quantum_kernel: QuantumKernel | null;
  no_quantum_reason: string | null;
}

/** A hybrid blueprint node (classical or quantum). */
export interface BlueprintNode {
  id: string;
  name: string;
  kind: "classical" | "quantum";
  description: string;
  inputs: string[];
  outputs: string[];
}

/** A directed edge in the hybrid blueprint. */
export interface BlueprintEdge {
  from_id: string;
  to_id: string;
}

/** Feasibility assessment (legacy fields kept). */
export interface Feasibility {
  qubit_count: number;
  estimated_depth: number;
  passes_limits: boolean;
}

/** Artifact of stage 3 (hybrid blueprint). */
export interface WorkflowBlueprint {
  nodes: BlueprintNode[];
  edges: BlueprintEdge[];
  feasibility: Feasibility;
}

/**
 * Unified trace record for a single pipeline stage.
 * `stage` takes one of: parse / analyze / blueprint / encode / codegen / execute /
 * combine / verify. `encode` and `combine` were added by the agentic pipeline
 * (Phase 1) and handle problem decomposition and sub-result merging respectively.
 * `codegen` and `execute` loop N times over the sub-problems and are distinguished
 * by `attempt` (zero-based).
 */
export interface StageTrace {
  id: number;
  stage: string;
  attempt: number;
  llm_input: Record<string, unknown> | null;
  llm_output: Record<string, unknown> | null;
  llm_model: string | null;
  duration_ms: number | null;
  token_usage: Record<string, unknown> | null;
  artifact: Record<string, unknown> | null;
  created_at: string;
  /** Inner tool-use loop for agent stages (codegen / verify); empty for non-agent stages. */
  rounds?: AgentRoundTrace[];
}

/** Trace of one round of an agent's tool-use loop: LLM thought + tool calls + tool results. */
export interface AgentRoundTrace {
  round_number: number;
  thought: string | null;
  tool_calls: Array<{
    tool_id?: string;
    tool_name: string;
    arguments?: Record<string, unknown>;
  }>;
  tool_results: Array<{
    tool_id?: string;
    tool_name: string;
    output: string;
    is_error?: boolean;
  }>;
  duration_ms: number | null;
  token_usage: Record<string, unknown> | null;
}

/** Summary of a single request. The verification status now also includes "off_spec" (the code solved the wrong problem). */
export interface RequestSummary {
  request_id: string;
  raw_text: string;
  final_status: "success" | "failed" | null;
  verification_status:
    | "cross_checked"
    | "unverified"
    | "mismatch"
    | "off_spec"
    | "failed"
    | null;
  created_at: string;
}

/** Complete pipeline trace payload. */
export interface FullTrace {
  request: RequestSummary;
  stages: StageTrace[];
}

/** Response body of POST /api/request. */
export interface CreateRequestResponse {
  request_id: string;
}

/** Request body of POST /api/request. Model selection is driven entirely by backend config; not sent in the request. */
export interface CreateRequestPayload {
  raw_text: string;
  language: Lang;
}
