/**
 * DetailInspector component.
 * Right-hand inspector panel that renders details for the current selection (a DAG node or a timeline stage event).
 */
import type { FullTrace } from "../api/types";
import { workflowBlueprint } from "../api/stages";
import { TraceEventDetail } from "./TraceEventDetail";
import type { TraceEventRef } from "./TraceTimeline";
import { useI18n } from "../i18n/useI18n";

/**
 * Discriminated-union type of the current selection:
 * "node"  — a DAG node is selected (id is the node ID);
 * "event" — a stage event on the timeline is selected (ref is the stage record id);
 * null    — nothing is selected.
 */
export type Selected =
  | { kind: "node"; id: string }
  | { kind: "event"; ref: TraceEventRef }
  | null;

/** Props for DetailInspector: `trace` is the full trace, `selected` is the current selection, `onClose` closes the panel. */
export interface DetailInspectorProps {
  trace: FullTrace;
  selected: Selected;
  onClose: () => void;
}

/**
 * Detail inspector component.
 * Branches on `selected.kind` to render different content:
 * null -> hint prompt; "node" -> DAG node parameters; "event" -> stage event details.
 */
export function DetailInspector({ trace, selected, onClose }: DetailInspectorProps) {
  const { t } = useI18n();
  let body;
  if (!selected) {
    body = <p className="text-sm text-slate-500">{t("inspector.hint")}</p>;
  } else if (selected.kind === "node") {
    const node = workflowBlueprint(trace)?.nodes?.find(
      (n) => n.id === selected.id,
    );
    body = node ? (
      <div className="space-y-2 text-sm">
        <h3 className="font-medium text-slate-900">{node.name}</h3>
        <p className="text-xs text-slate-500">{t("inspector.node", { id: node.id })}</p>
        <p className="text-xs text-slate-600">
          <span className="font-medium">{t("inspector.nodeKind")}</span>
          {node.kind === "quantum" ? t("dag.quantum") : t("dag.classical")}
        </p>
        <p className="text-xs text-slate-700">{node.description}</p>
        {node.inputs.length > 0 && (
          <p className="text-xs text-slate-600">
            <span className="font-medium">{t("inspector.nodeInputs")}</span>
            {node.inputs.join(", ")}
          </p>
        )}
        {node.outputs.length > 0 && (
          <p className="text-xs text-slate-600">
            <span className="font-medium">{t("inspector.nodeOutputs")}</span>
            {node.outputs.join(", ")}
          </p>
        )}
      </div>
    ) : (
      <p className="text-sm text-slate-500">{t("inspector.notFound")}</p>
    );
  } else {
    body = <TraceEventDetail trace={trace} selectedId={selected.ref} />;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-[18px] py-3.5">
        <h3 className="text-[13px] font-bold text-slate-600">{t("inspector.title")}</h3>
        <button
          type="button"
          onClick={onClose}
          className="px-1 text-lg text-slate-500 hover:text-blue-600"
          aria-label={t("inspector.close")}
        >
          ✕
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-[18px]">{body}</div>
    </div>
  );
}
