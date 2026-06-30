import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { LanguageProvider } from "../i18n/LanguageProvider";
import type { Lang } from "../i18n/types";

/** Render a component wrapped in LanguageProvider; defaults to Chinese for convenience in tests. */
export function renderWithI18n(ui: ReactElement, lang: Lang = "zh") {
  return render(<LanguageProvider initialLang={lang}>{ui}</LanguageProvider>);
}
