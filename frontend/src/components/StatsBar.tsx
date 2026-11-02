// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * StatsBar component.
 * A four-cell card row: stage count, qubit count (reduced), result value, and wall-clock time.
 */
import type { FullTrace } from "../api/types";
import { execResult, quantumOpportunity } from "../api/stages";
import { useI18n } from "../i18n/useI18n";

export interface StatsBarProps {
  trace: FullTrace;
}

function Stat({ value, label, color }: { value: string; label: string; color: string }) {
  return (
    <div className="rounded-[10px] border border-slate-200 bg-white p-3.5 text-center shadow-sm">
      <div className={`text-[26px] font-extrabold ${color}`}>{value}</div>
      <div className="mt-[3px] text-[11px] font-semibold text-slate-500">{label}</div>
    </div>
  );
}

export function StatsBar({ trace }: StatsBarProps) {
  const { t } = useI18n();

  const stageCount = trace.stages.length;

  const kernel = quantumOpportunity(trace)?.quantum_kernel;
  const qubits =
    typeof kernel?.reduced_qubits === "number" ? String(kernel.reduced_qubits) : "—";

  const exec = execResult(trace);
  const valRaw = exec?.result?.value;
  const value = typeof valRaw === "number" ? valRaw.toFixed(3) : "—";

  const wallRaw = exec?.metrics?.wall_time_s;
  const wall = typeof wallRaw === "number" ? `${wallRaw.toFixed(1)}s` : "—";

  return (
    <div className="grid grid-cols-4 gap-2.5">
      <Stat value={String(stageCount)} label={t("stats.stages")} color="text-blue-600" />
      <Stat value={qubits} label={t("stats.qubits")} color="text-cyan-600" />
      <Stat value={value} label={t("stats.value")} color="text-emerald-600" />
      <Stat value={wall} label={t("stats.wallTime")} color="text-amber-600" />
    </div>
  );
}
