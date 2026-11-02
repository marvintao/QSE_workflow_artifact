// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * SolutionCard component.
 * Embedded inside a chat message to summarise the "quantum opportunity":
 * algorithm, sub-problem, scale, and execution result.
 * When `quantum_kernel` is null, falls back to displaying `no_quantum_reason`.
 */
import type { FullTrace } from "../api/types";
import { execResult, quantumOpportunity } from "../api/stages";
import { useI18n } from "../i18n/useI18n";

export interface SolutionCardProps {
  trace: FullTrace;
}

export function SolutionCard({ trace }: SolutionCardProps) {
  const { t } = useI18n();

  const opp = quantumOpportunity(trace);
  const exec = execResult(trace);
  const valueRaw = exec?.result?.value;
  const value = typeof valueRaw === "number" ? valueRaw : null;

  // No quantum-solvable component — honestly surface no_quantum_reason
  if (opp && opp.quantum_kernel === null) {
    return (
      <div className="mt-2 max-w-[340px] rounded-[10px] border border-amber-200 bg-amber-50 p-3 shadow-sm">
        <div className="text-xs font-bold text-amber-700">
          {t("opportunity.noQuantumTitle")}
        </div>
        {opp.no_quantum_reason && (
          <div className="mt-1 text-xs text-amber-800">
            <span className="text-amber-600">{t("opportunity.noQuantumReason")}</span>
            {opp.no_quantum_reason}
          </div>
        )}
      </div>
    );
  }

  const kernel = opp?.quantum_kernel;
  return (
    <div className="mt-2 max-w-[340px] rounded-[10px] border border-slate-200 bg-white p-3 shadow-sm">
      <div className="text-xs font-bold text-blue-600">{t("opportunity.title")}</div>

      <div className="mt-2 text-xs">
        <span className="text-slate-500">{t("opportunity.algorithm")}</span>
        <span className="font-semibold text-slate-900">{kernel?.algorithm ?? "—"}</span>
      </div>
      {kernel?.algorithm_rationale && (
        <div className="mt-1 text-xs text-slate-700">
          <span className="text-slate-500">{t("opportunity.rationale")}</span>
          {kernel.algorithm_rationale}
        </div>
      )}
      {kernel?.subproblem && (
        <div className="mt-1 text-xs text-slate-700">
          <span className="text-slate-500">{t("opportunity.subproblem")}</span>
          {kernel.subproblem}
        </div>
      )}
      {kernel && (
        <div className="mt-1 text-[11px] text-slate-500">
          {kernel.needs_reduction
            ? t("opportunity.scale", {
                reduced: kernel.reduced_qubits,
                full: kernel.full_scale_qubits,
              })
            : t("opportunity.scaleFull", { count: kernel.reduced_qubits })}
        </div>
      )}
      {kernel?.needs_reduction && kernel.reduction_note && (
        <div className="mt-1 rounded bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
          <span className="font-medium">{t("opportunity.reductionNote")}</span>
          {kernel.reduction_note}
        </div>
      )}

      <div className="mt-3 border-t border-slate-200 pt-2 text-xs">
        <span className="text-slate-500">{t("opportunity.execResult")}</span>
        {exec ? (
          <>
            <span
              className={
                exec.status === "success"
                  ? "font-semibold text-emerald-600"
                  : "font-semibold text-red-600"
              }
            >
              {exec.status === "success" ? t("opportunity.success") : exec.status}
            </span>
            {value !== null && (
              <div className="mt-1 text-lg font-bold text-slate-900">
                {value.toFixed(3)}
              </div>
            )}
          </>
        ) : (
          <span className="text-slate-500">{t("opportunity.noResult")}</span>
        )}
      </div>
    </div>
  );
}
