// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * TraceEventDetail component.
 * Looks up the selected stage record by id in the stages array and renders its detail fields.
 */
import type { AgentRoundTrace, FullTrace } from "../api/types";
import type { TraceEventRef } from "./TraceTimeline";
import { useI18n } from "../i18n/useI18n";
import type { TranslationKey } from "../i18n/types";

/** Props for TraceEventDetail: `trace` is the full trace, `selectedId` is the id of the selected stage record. */
export interface TraceEventDetailProps {
  trace: FullTrace;
  selectedId: TraceEventRef | null;
}

/** Translation keys for each stage label (covers all 9 agentic stages, including global_review). */
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

/** Collapsible JSON block: a <details> wrapping pretty-printed JSON, used to render arbitrary trace fields.
 *  `max-h-96` gives long artifact / llm_output more visible height, with overflow scrolling inside. */
function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <details className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
      <summary className="cursor-pointer font-medium text-slate-700">{label}</summary>
      <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-words text-slate-700">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}

/** Small card for one agent iteration: thought + tool-call list + tool-result list. */
function AgentRoundCard({ round }: { round: AgentRoundTrace }) {
  const { t } = useI18n();
  return (
    <div className="rounded border border-slate-200 bg-white px-3 py-2 text-xs space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-slate-700">
          {t("detail.round", { n: round.round_number })}
        </span>
        <span className="text-[10px] text-slate-500">
          {round.duration_ms ?? 0} ms
        </span>
      </div>
      {round.thought && (
        <p className="whitespace-pre-wrap break-words text-slate-700">
          {round.thought}
        </p>
      )}
      {round.tool_calls.length > 0 && (
        <div className="space-y-1">
          {round.tool_calls.map((tc, i) => {
            const tr = round.tool_results[i];
            const errored = tr?.is_error;
            return (
              <div key={i} className="rounded bg-slate-50 px-2 py-1">
                <div className="flex items-center gap-1.5">
                  <span className="font-mono font-semibold text-slate-800">
                    {tc.tool_name}
                  </span>
                  {tc.arguments && Object.keys(tc.arguments).length > 0 && (
                    <span className="truncate font-mono text-[10px] text-slate-500">
                      ({JSON.stringify(tc.arguments).slice(0, 80)})
                    </span>
                  )}
                </div>
                {tr && (
                  <pre className={`mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] ${
                    errored ? "text-rose-700" : "text-slate-600"
                  }`}>
                    {tr.output}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Trace event detail component.
 * All stages share the same StageTrace structure, so they share a uniform layout:
 * stage name + model/duration metadata + collapsible JSON blocks for
 * artifact / llm_input / llm_output / token_usage.
 */
export function TraceEventDetail({ trace, selectedId }: TraceEventDetailProps) {
  const { t } = useI18n();

  if (selectedId === null) {
    return <p className="text-sm text-slate-500">{t("detail.emptyHint")}</p>;
  }

  const row = trace.stages.find((s) => s.id === selectedId);
  if (!row) return null;

  const labelKey = STAGE_LABEL[row.stage];
  const label = labelKey ? t(labelKey) : row.stage;

  return (
    <div className="space-y-2 text-sm">
      <h3 className="font-medium">
        {label}
        {row.attempt > 0 && (
          <span className="ml-2 text-xs font-normal text-amber-600">
            {t("timeline.attempt", { n: row.attempt })}
          </span>
        )}
      </h3>
      <p className="text-xs text-slate-500">
        {row.llm_model ?? "—"} · {row.duration_ms ?? 0} ms
      </p>
      {row.token_usage && <JsonBlock label={t("detail.tokenUsage")} value={row.token_usage} />}
      <JsonBlock label={t("detail.artifact")} value={row.artifact} />
      <JsonBlock label={t("detail.llmInput")} value={row.llm_input} />
      <JsonBlock label={t("detail.llmOutput")} value={row.llm_output} />
      {row.rounds && row.rounds.length > 0 && (
        <details open className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs">
          <summary className="cursor-pointer font-medium text-amber-800">
            {t("detail.agentRounds", { n: row.rounds.length })}
          </summary>
          <div className="mt-2 space-y-1.5">
            {row.rounds.map((r) => (
              <AgentRoundCard key={r.round_number} round={r} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
