// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * WorkflowDAG component.
 * Visualizes the hybrid workflow blueprint (classical + quantum nodes) as a React Flow node graph.
 */
import { useMemo } from "react";
import { ReactFlow, Background, Controls, type Node, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { FullTrace } from "../api/types";
import { workflowBlueprint } from "../api/stages";
import { useI18n } from "../i18n/useI18n";

export interface WorkflowDAGProps {
  trace: FullTrace;
  onNodeClick?: (id: string) => void;
}

/** Quantum nodes use a blue outline to stand out; classical nodes use gray. Distinguished by `kind`. */
const KIND_STYLE = {
  classical: {
    border: "1px solid #cbd5e1",
    background: "#fff",
  },
  quantum: {
    border: "2px solid #2563eb",
    background: "#eff6ff",
  },
} as const;

export function WorkflowDAG({ trace, onNodeClick }: WorkflowDAGProps) {
  const { t } = useI18n();
  const blueprint = workflowBlueprint(trace);

  const { nodes, edges } = useMemo(() => {
    if (!blueprint) return { nodes: [] as Node[], edges: [] as Edge[] };

    const nodes: Node[] = blueprint.nodes.map((n, i) => {
      const kindLabel = n.kind === "quantum" ? t("dag.quantum") : t("dag.classical");
      const style = KIND_STYLE[n.kind];
      return {
        id: n.id,
        position: { x: 80 + i * 220, y: 120 },
        data: { label: `[${kindLabel}] ${n.name}\n(${n.id})` },
        style: {
          width: 180,
          padding: 12,
          borderRadius: 6,
          whiteSpace: "pre-wrap" as const,
          fontFamily: "monospace",
          fontSize: 12,
          ...style,
        },
      };
    });
    const edges: Edge[] = blueprint.edges.map((e, i) => ({
      id: `e${i}`,
      source: e.from_id,
      target: e.to_id,
      animated: false,
    }));
    return { nodes, edges };
  }, [blueprint, t]);

  if (!blueprint) {
    return (
      <div className="rounded border border-slate-200 bg-white p-6 text-slate-500">
        {t("dag.empty")}
      </div>
    );
  }

  return (
    <div className="h-96 rounded border border-slate-200 bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        onNodeClick={(_, node) => onNodeClick?.(node.id)}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
