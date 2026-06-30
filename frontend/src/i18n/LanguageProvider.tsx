import { createContext, useCallback, useMemo, useState, type ReactNode } from "react";
import type { Lang } from "./types";

const STORAGE_KEY = "qwf-lang";

/** Context value: the current language and a setter. */
export interface LanguageContextValue {
  lang: Lang;
  setLang: (next: Lang) => void;
}

/** Language context. Defaults to null so useI18n can detect missing Provider wrapping and throw. */
export const LanguageContext = createContext<LanguageContextValue | null>(null);

/** Resolve the initial language: prefer the persisted localStorage value, otherwise infer from the browser language. */
function detectLang(): Lang {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "en" || saved === "zh") return saved;
  return navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

export interface LanguageProviderProps {
  children: ReactNode;
  /** For tests: specify the initial language directly, bypassing localStorage / browser detection. */
  initialLang?: Lang;
}

/** Language context Provider: holds the current language and writes back to localStorage on change. */
export function LanguageProvider({ children, initialLang }: LanguageProviderProps) {
  // Lazy initializer: evaluated only on mount; later changes to `initialLang` are ignored by design
  const [lang, setLangState] = useState<Lang>(() => initialLang ?? detectLang());

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const value = useMemo(() => ({ lang, setLang }), [lang, setLang]);
  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}
