/**
 * VerificationBadge component.
 * Renders a colored badge for the request's verification status
 * (cross-checked / unverified / mismatch / off-spec / failed).
 */
import type { RequestSummary } from "../api/types";
import { useI18n } from "../i18n/useI18n";
import type { TranslationKey } from "../i18n/types";

/** Props for VerificationBadge: `status` is the request verification status; when null the component renders nothing. */
export interface VerificationBadgeProps {
  status: RequestSummary["verification_status"];
}

/** Translation key and color styles for each verification status. */
const STYLE: Record<
  NonNullable<RequestSummary["verification_status"]>,
  { key: TranslationKey; className: string }
> = {
  cross_checked: {
    key: "verification.crossChecked",
    className: "border-emerald-600 bg-emerald-50 text-emerald-700",
  },
  unverified: {
    key: "verification.unverified",
    className: "border-slate-300 bg-slate-50 text-slate-600",
  },
  mismatch: {
    key: "verification.mismatch",
    className: "border-amber-500 bg-amber-50 text-amber-700",
  },
  off_spec: {
    key: "verification.offSpec",
    className: "border-rose-500 bg-rose-50 text-rose-700",
  },
  failed: {
    key: "verification.failed",
    className: "border-red-500 bg-red-50 text-red-700",
  },
};

/**
 * Verification-status badge component.
 * Renders nothing when status is null; otherwise maps the status to its label and color.
 */
export function VerificationBadge({ status }: VerificationBadgeProps) {
  const { t } = useI18n();
  if (!status) return null;
  const style = STYLE[status];
  return (
    <span
      data-testid="verification-badge"
      className={`rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${style.className}`}
    >
      {t(style.key)}
    </span>
  );
}
