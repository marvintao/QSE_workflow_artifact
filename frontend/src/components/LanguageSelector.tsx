import { useI18n } from "../i18n/useI18n";
import type { Lang } from "../i18n/types";

/** Each language is labeled in its own language (standard i18n convention). */
const OPTIONS: { value: Lang; label: string }[] = [
  { value: "zh", label: "中文" },
  { value: "en", label: "English" },
];

/** Header language switch control: segmented buttons that switch and persist the language on click. */
export function LanguageSelector() {
  const { lang, setLang } = useI18n();
  return (
    <div className="flex overflow-hidden rounded-lg border border-slate-300">
      {OPTIONS.map((opt) => {
        const active = opt.value === lang;
        return (
          <button
            key={opt.value}
            type="button"
            aria-pressed={active}
            onClick={() => setLang(opt.value)}
            className={`px-2.5 py-1 text-xs font-semibold ${
              active
                ? "bg-blue-600 text-white"
                : "bg-white text-slate-600 hover:bg-blue-50 hover:text-blue-600"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
