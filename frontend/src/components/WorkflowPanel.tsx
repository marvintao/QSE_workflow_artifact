// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * WorkflowPanel component.
 * The central main panel: aggregates the pipeline status bar, DAG visualization,
 * stats bar, code viewer, and the collapsible stage timeline.
 */
import { useState } from "react";
import type { FullTrace } from "../api/types";
import { generatedCode } from "../api/stages";
import { useI18n } from "../i18n/useI18n";
import { CodeViewer } from "./CodeViewer";
import { PipelineBar } from "./PipelineBar";
import { StatsBar } from "./StatsBar";
import { TraceTimeline, type TraceEventRef } from "./TraceTimeline";
import { WorkflowDAG } from "./WorkflowDAG";

/**
 * Props for WorkflowPanel.
 * When `trace` is null, renders the waiting placeholder view.
 * `onSelectNode` / `onSelectEvent` propagate the selection back to App, which is consumed by DetailInspector.
 */
export interface WorkflowPanelProps {
  trace: FullTrace | null;
  onSelectNode: (id: string) => void;
  onSelectEvent: (ref: TraceEventRef) => void;
  selectedEventId: TraceEventRef | null;
}

/**
 * Workflow main panel component.
 * Owns the stage-timeline collapse state (`logOpen`); when `trace` is null it renders a waiting/guide screen.
 */
export function WorkflowPanel({
  trace,
  onSelectNode,
  onSelectEvent,
  selectedEventId,
}: WorkflowPanelProps) {
  const { t } = useI18n();
  const [logOpen, setLogOpen] = useState(true);

  if (!trace) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3.5 text-center text-slate-500">
        <div className="text-[52px] opacity-30">⚛</div>
        <h3 className="text-base text-slate-600">{t("workflow.emptyTitle")}</h3>
        <p className="max-w-md text-[13px] leading-relaxed">
          {t("workflow.emptyDesc")}
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-3.5 overflow-y-auto p-[18px]">
      <PipelineBar trace={trace} />
      <WorkflowDAG trace={trace} onNodeClick={onSelectNode} />
      <StatsBar trace={trace} />
      <CodeViewer code={generatedCode(trace)} />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <button
          type="button"
          onClick={() => setLogOpen((v) => !v)}
          className="flex w-full items-center justify-between bg-slate-50 px-4 py-3 text-left hover:bg-blue-50"
        >
          <span className="text-[13px] font-bold text-slate-600">{t("workflow.stageTimeline")}</span>
          <span className="text-xs text-slate-500">
            {logOpen ? t("workflow.collapse") : t("workflow.expand")}
          </span>
        </button>
        {logOpen && (
          <div className="p-3">
            <TraceTimeline
              trace={trace}
              onSelect={onSelectEvent}
              selectedId={selectedEventId}
            />
          </div>
        )}
      </div>
    </div>
  );
}
