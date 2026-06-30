/**
 * Stage trace helper module.
 * The backend's `stages` array distinguishes pipeline stages by the `stage` field;
 * this module extracts artifacts by stage name.
 */
import type {
  FullTrace,
  ParsedIntent,
  QuantumOpportunity,
  StageTrace,
  WorkflowBlueprint,
} from "./types";

/** Fixed stage order shown in the main progress bar (the 9 stages of the agentic
 *  pipeline, including global_review and verify).
 *  codegen + global_review form an internal loop: the reviewer may emit "revise" to
 *  send work back to codegen for rewriting, up to N rounds; the UI renders them as a
 *  bidirectional-arrow group.
 *  codegen + execute also loop per sub-problem, distinguished by `attempt`; the
 *  progress bar only checks whether a stage has appeared and ignores `attempt`. */
export const STAGE_ORDER = [
  "parse",
  "analyze",
  "blueprint",
  "encode",
  "codegen",
  "global_review",
  "execute",
  "combine",
  "verify",
] as const;

/** The two ends of the codegen <-> global_review internal loop; rendered as a group in the UI. */
export const REVIEW_LOOP = ["codegen", "global_review"] as const;

/** Union type of a single primary stage identifier. */
export type StageName = (typeof STAGE_ORDER)[number];

/**
 * Get the "final" record for a given stage (the entry with the highest attempt).
 * The self-repair loop can produce multiple rows for codegen / execute; this returns the last one.
 */
export function lastStage(
  trace: FullTrace,
  stage: StageName,
): StageTrace | undefined {
  return trace.stages
    .filter((s) => s.stage === stage)
    .reduce<StageTrace | undefined>((best, cur) => {
      if (!best || cur.attempt > best.attempt) return cur;
      return best;
    }, undefined);
}

/** Get all records for a given stage, sorted by attempt ascending. */
export function allStages(
  trace: FullTrace,
  stage: StageName,
): StageTrace[] {
  return trace.stages
    .filter((s) => s.stage === stage)
    .sort((a, b) => a.attempt - b.attempt);
}

/** Artifact of the parse stage: the parsed user intent. */
export function parsedIntent(trace: FullTrace): ParsedIntent | undefined {
  return lastStage(trace, "parse")?.artifact as ParsedIntent | undefined;
}

/** Artifact of the analyze stage: the quantum opportunity (algorithm, kernel spec, scale estimate). */
export function quantumOpportunity(
  trace: FullTrace,
): QuantumOpportunity | undefined {
  return lastStage(trace, "analyze")?.artifact as
    | QuantumOpportunity
    | undefined;
}

/** Artifact of the blueprint stage: the hybrid classical + quantum workflow blueprint. */
export function workflowBlueprint(
  trace: FullTrace,
): WorkflowBlueprint | undefined {
  return lastStage(trace, "blueprint")?.artifact as
    | WorkflowBlueprint
    | undefined;
}

/** The generated code string inside the final artifact of the codegen stage. */
export function generatedCode(trace: FullTrace): string | null {
  const artifact = lastStage(trace, "codegen")?.artifact as
    | { code?: string }
    | undefined;
  return typeof artifact?.code === "string" ? artifact.code : null;
}

/** Local shape of the execute stage artifact. */
export interface ExecArtifact {
  status: "success" | "runtime_error" | "resource_limit";
  result: Record<string, unknown> | null;
  stderr_excerpt: string | null;
  metrics: Record<string, unknown> | null;
}

/** Final artifact of the execute stage. */
export function execResult(trace: FullTrace): ExecArtifact | undefined {
  return lastStage(trace, "execute")?.artifact as ExecArtifact | undefined;
}

/** Shape of the encode stage artifact. */
export interface EncodingPlan {
  strategy: string;
  strategy_rationale: string;
  sub_problems: Array<{ id: string; instance: Record<string, unknown>;
                         role: string }>;
  combine_method: string;
}

/** Final artifact of the encode stage (decomposition strategy + sub-problem list). */
export function encodingPlan(trace: FullTrace): EncodingPlan | undefined {
  return lastStage(trace, "encode")?.artifact as EncodingPlan | undefined;
}

/** Shape of the combine stage artifact. */
export interface CombinedResult {
  value: number | Record<string, unknown>;
  instance: Record<string, unknown>;
  subresults_summary: Array<Record<string, unknown>>;
  combine_log: string;
}

/** Final artifact of the combine stage (the merged, full solution). */
export function combinedResult(trace: FullTrace): CombinedResult | undefined {
  return lastStage(trace, "combine")?.artifact as CombinedResult | undefined;
}

/** Artifact of the global_review stage: the reviewer's verdict + feedback between codegen and execute. */
export interface GlobalReviewArtifact {
  verdict: "approve" | "revise";
  feedback: string;
}

/** Artifact of the global_review stage. With multiple attempts, returns the latest verdict. */
export function globalReviewArtifact(
  trace: FullTrace,
): GlobalReviewArtifact | undefined {
  return lastStage(trace, "global_review")?.artifact as
    | GlobalReviewArtifact
    | undefined;
}

/** All attempts of global_review (used to surface feedback history across multiple revise rounds). */
export function globalReviewRounds(
  trace: FullTrace,
): Array<{ attempt: number; artifact: GlobalReviewArtifact }> {
  return allStages(trace, "global_review").map((s) => ({
    attempt: s.attempt,
    artifact: s.artifact as unknown as GlobalReviewArtifact,
  }));
}

/** Artifact of the verify stage: the LLM judge's verdict and rationale. */
export interface VerifyArtifact {
  verification_status:
    | "cross_checked"
    | "unverified"
    | "mismatch"
    | "off_spec"
    | "failed";
  reason: string;
}

/** Artifact of the verify stage. */
export function verifyArtifact(trace: FullTrace): VerifyArtifact | undefined {
  return lastStage(trace, "verify")?.artifact as VerifyArtifact | undefined;
}
