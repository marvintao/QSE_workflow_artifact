import { useContext } from "react";
import { LanguageContext } from "./LanguageProvider";
import type { Lang, TranslationKey } from "./types";
import { zh } from "./zh";
import { en } from "./en";

const DICTS: Record<Lang, Record<TranslationKey, string>> = { zh, en };

/** Replace "{name}" placeholders with the matching value from `vars`. */
function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{([a-zA-Z]+)\}/g, (whole, name) =>
    name in vars ? String(vars[name]) : whole,
  );
}

/** i18n hook: returns the current language, the setter, and the `t()` translation function. Must be used inside a LanguageProvider. */
export function useI18n() {
  const ctx = useContext(LanguageContext);
  if (ctx === null) {
    throw new Error("useI18n 必须在 <LanguageProvider> 内部使用");
  }
  const { lang, setLang } = ctx;
  const t = (key: TranslationKey, vars?: Record<string, string | number>): string =>
    interpolate(DICTS[lang][key], vars);
  return { lang, setLang, t };
}
