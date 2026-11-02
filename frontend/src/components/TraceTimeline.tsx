// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * TraceTimeline component.
 * Renders the unified stages array as a clickable execution timeline in stage order
 * (including the multiple attempts produced by the self-repair loop).
 */
import type { FullTrace, StageTrace } from "../api/types";
import { STAGE_ORDER } from "../api/stages";
import { useI18n } from "../i18n/useI18n";
import type { TranslationKey } from "../i18n/types";

/** Timeline event reference: identified directly by the stage record's database id. */
export type TraceEventRef = number;

/** Props for TraceTimeline: `trace` is the data source, `onSelect` handles click selection, `selectedId` drives current highlight. */
export interface TraceTimelineProps {
  trace: FullTrace;
  onSelect: (ref: TraceEventRef) => void;
  selectedId: TraceEventRef | null;
}

/** Translation keys for each stage label. */
const STAGE_LABEL: Record<string, TranslationKey> = {
  parse: "pipeline.parse",
  analyze: "pipeline.analyze",
  blueprint: "pipeline.blueprint",
  codegen: "pipeline.codegen",
  execute: "pipeline.execute",
  verify: "pipeline.verify",
};

/**
 * Sort the stages array by the fixed stage order in STAGE_ORDER, then by ascending attempt,
 * producing a stable timeline display order (repeated codegen / execute entries produced by
 * the self-repair loop sit adjacent to one another).
 */
function ordered(stages: StageTrace[]): StageTrace[] {
  const rank = (s: string) => {
    const i = STAGE_ORDER.indexOf(s as (typeof STAGE_ORDER)[number]);
    return i === -1 ? STAGE_ORDER.length : i;
  };
  return [...stages].sort(
    (a, b) => rank(a.stage) - rank(b.stage) || a.attempt - b.attempt,
  );
}

/**
 * Execution timeline component.
 * Renders stage records as an interactive list in pipeline order; clicking an entry fires onSelect
 * to update the current selection.
 */
export function TraceTimeline({ trace, onSelect, selectedId }: TraceTimelineProps) {
  const { t } = useI18n();
  const events = ordered(trace.stages);

  return (
    <ul className="space-y-1">
      {events.map((e) => {
        const labelKey = STAGE_LABEL[e.stage];
        const label = labelKey ? t(labelKey) : e.stage;
        const meta = e.duration_ms ? `${e.duration_ms} ms` : "";
        return (
          <li
            key={e.id}
            onClick={() => onSelect(e.id)}
            className={`cursor-pointer rounded px-3 py-2 text-sm hover:bg-slate-100 ${
              selectedId === e.id ? "bg-slate-100 ring-1 ring-slate-300" : ""
            }`}
          >
            <span className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-500" />
            <span className="font-medium">{label}</span>
            {e.attempt > 0 && (
              <span className="ml-2 text-xs text-amber-600">
                {t("timeline.attempt", { n: e.attempt })}
              </span>
            )}
            {meta && <span className="ml-2 text-xs text-slate-500">· {meta}</span>}
          </li>
        );
      })}
    </ul>
  );
}
