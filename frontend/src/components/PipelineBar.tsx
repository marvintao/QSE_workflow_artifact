/**
 * PipelineBar component.
 *
 * Renders the 9 stages of the agentic pipeline as a badge + arrow strip
 * (parse -> analyze -> blueprint -> encode -> codegen <-> global_review -> execute -> combine -> verify).
 * codegen and global_review form an internal loop: the reviewer may emit "revise" to send work back
 * to codegen for rewriting, up to N rounds; the UI draws them as a group with bidirectional arrows
 * and displays the round count (inferred from global_review's attempts).
 *
 * State semantics:
 *  - done (green): the stage has at least one stage_trace row persisted to the DB.
 *  - running (amber + pulsing): the stage is the first in STAGE_ORDER not yet present, while the
 *    pipeline has not reached a terminal state.
 *  - pending (gray): any other stage that has not yet appeared.
 *
 * The "N / 9" header shows the count of completed stages (denominator = STAGE_ORDER.length).
 */
import type { FullTrace } from "../api/types";
import { STAGE_ORDER, REVIEW_LOOP } from "../api/stages";
import type { StageName } from "../api/stages";
import { useI18n } from "../i18n/useI18n";
import type { TranslationKey } from "../i18n/types";

/** Props for PipelineBar: `trace` is the full trace used to infer each stage's state. */
export interface PipelineBarProps {
  trace: FullTrace;
}

/** Translation keys for each stage label (covers all 9 entries of STAGE_ORDER). */
const STAGE_LABEL: Record<string, TranslationKey> = {
  parse: "pipeline.parse",
  analyze: "pipeline.analyze",
  blueprint: "pipeline.blueprint",
  encode: "pipeline.encode",
  codegen: "pipeline.codegen",
  global_review: "pipeline.global_review",
  execute: "pipeline.execute",
  combine: "pipeline.combine",
  verify: "pipeline.verify",
};

type StageState = "done" | "running" | "pending";

/** Render a single stage badge. Styling differs slightly inside vs. outside the loop. */
function StageBadge({
  stage, state, label, dense = false,
}: { stage: StageName; state: StageState; label: string; dense?: boolean }) {
  const cls =
    state === "done"
      ? "border-emerald-600 bg-emerald-50 text-emerald-700"
      : state === "running"
        ? "border-amber-500 bg-amber-50 text-amber-700 animate-pulse"
        : "border-slate-300 bg-white text-slate-500";
  return (
    <div
      data-testid="pipeline-step"
      data-stage={stage}
      data-state={state}
      className={`rounded-2xl border ${dense ? "px-2" : "px-3"} py-[5px] text-[11px] font-bold ${cls}`}
    >
      {label}
    </div>
  );
}

/** Render a one-way arrow (between stages). */
function Arrow({ active }: { active: boolean }) {
  const color = active ? "text-emerald-600" : "text-slate-300";
  return (
    <span
      aria-hidden="true"
      className={`select-none text-[14px] font-bold ${color}`}
    >
      →
    </span>
  );
}

/**
 * Pipeline status bar component.
 * Infers the state of each stage (done / running / pending) and renders progress in three styles.
 * codegen and global_review are grouped into a "review loop" sub-frame with a bidirectional arrow.
 */
export function PipelineBar({ trace }: PipelineBarProps) {
  const { t } = useI18n();
  // Use a Set of stages already present for O(1) lookup
  const present = new Set(trace.stages.map((s) => s.stage));
  const finished = trace.request.final_status !== null;
  // The "currently running" stage = the first one in STAGE_ORDER that has not appeared; absent once the pipeline reaches a terminal state
  const runningStage = finished
    ? null
    : STAGE_ORDER.find((s) => !present.has(s)) ?? null;
  // Number of completed stages / total length (including global_review + verify)
  const doneCount = STAGE_ORDER.filter((s) => present.has(s)).length;

  // Derive the state for each stage
  const stateOf = (stage: StageName): StageState =>
    present.has(stage) ? "done" : stage === runningStage ? "running" : "pending";

  // How many rounds the codegen <-> global_review loop actually ran, inferred from global_review's attempt count
  const reviewAttempts = trace.stages.filter(
    (s) => s.stage === "global_review",
  ).length;

  // Split STAGE_ORDER into "single-stage blocks (outside the loop)" + "loop block" for rendering
  const renderItems: Array<
    | { kind: "single"; stage: StageName }
    | { kind: "loop" }
  > = [];
  for (let i = 0; i < STAGE_ORDER.length; i++) {
    const s = STAGE_ORDER[i];
    if (s === "codegen") {
      // codegen is immediately followed by global_review; merge them into a loop block
      renderItems.push({ kind: "loop" });
      i++; // skip global_review
    } else {
      renderItems.push({ kind: "single", stage: s });
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-slate-500">
          {t("pipeline.progress", {
            done: doneCount, total: STAGE_ORDER.length,
          })}
        </span>
        {runningStage && (
          <span className="flex items-center gap-1 text-[11px] font-semibold text-amber-700">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
            {t("pipeline.runningPrefix")} {t(STAGE_LABEL[runningStage])}
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {renderItems.map((item, idx) => {
          // If the next stage is already done, mark the preceding arrow as active (green)
          const nextStage =
            idx + 1 < renderItems.length
              ? (renderItems[idx + 1].kind === "single"
                  ? (renderItems[idx + 1] as { stage: StageName }).stage
                  : REVIEW_LOOP[0])
              : null;
          const showArrowAfter = idx < renderItems.length - 1;
          const arrowActive = nextStage ? present.has(nextStage) : false;

          if (item.kind === "single") {
            return (
              <div key={item.stage} className="flex items-center gap-1.5">
                <StageBadge
                  stage={item.stage}
                  state={stateOf(item.stage)}
                  label={t(STAGE_LABEL[item.stage])}
                />
                {showArrowAfter && <Arrow active={arrowActive} />}
              </div>
            );
          }
          // Loop block: codegen <-> global_review, wrapped in a dashed sub-frame
          const cgState = stateOf("codegen");
          const grState = stateOf("global_review");
          const loopActive = cgState === "done" || grState === "done";
          return (
            <div key="review-loop" className="flex items-center gap-1.5">
              <div
                data-testid="review-loop"
                data-state={loopActive ? "active" : "pending"}
                className={`flex items-center gap-1 rounded-lg border border-dashed px-1.5 py-1 ${
                  loopActive ? "border-emerald-400 bg-emerald-50/40" : "border-slate-300 bg-slate-50/40"
                }`}
              >
                <StageBadge
                  stage="codegen"
                  state={cgState}
                  label={t(STAGE_LABEL.codegen)}
                  dense
                />
                <span
                  aria-hidden="true"
                  className={`select-none text-[12px] font-bold ${
                    loopActive ? "text-emerald-600" : "text-slate-400"
                  }`}
                  title={t("pipeline.reviewLoop")}
                >
                  ⇄
                </span>
                <StageBadge
                  stage="global_review"
                  state={grState}
                  label={t(STAGE_LABEL.global_review)}
                  dense
                />
                {reviewAttempts > 1 && (
                  <span
                    data-testid="review-rounds"
                    className="ml-1 rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700"
                  >
                    {t("pipeline.reviewRounds", { n: reviewAttempts })}
                  </span>
                )}
              </div>
              {showArrowAfter && <Arrow active={arrowActive} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
