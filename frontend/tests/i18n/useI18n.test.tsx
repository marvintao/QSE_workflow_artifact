import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguageProvider } from "../../src/i18n/LanguageProvider";
import { useI18n } from "../../src/i18n/useI18n";

function Probe() {
  const { lang, setLang, t } = useI18n();
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <span data-testid="title">{t("app.title")}</span>
      <span data-testid="interp">{t("chat.pipelineFailed", { error: "boom" })}</span>
      <button onClick={() => setLang(lang === "zh" ? "en" : "zh")}>toggle</button>
    </div>
  );
}

describe("useI18n", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it("translates and interpolates in the initial language", () => {
    render(
      <LanguageProvider initialLang="zh">
        <Probe />
      </LanguageProvider>
    );
    expect(screen.getByTestId("title").textContent).toBe("量子工作流平台");
    expect(screen.getByTestId("interp").textContent).toBe("流水线失败:boom");
  });

  it("translates in English", () => {
    render(
      <LanguageProvider initialLang="en">
        <Probe />
      </LanguageProvider>
    );
    expect(screen.getByTestId("title").textContent).toBe("Quantum Workflow Platform");
    expect(screen.getByTestId("interp").textContent).toBe("Pipeline failed: boom");
  });

  it("setLang switches language and persists to localStorage", async () => {
    render(
      <LanguageProvider initialLang="zh">
        <Probe />
      </LanguageProvider>
    );
    await userEvent.click(screen.getByRole("button", { name: "toggle" }));
    expect(screen.getByTestId("lang").textContent).toBe("en");
    expect(localStorage.getItem("qwf-lang")).toBe("en");
  });

  it("reads a persisted language from localStorage when no initialLang is given", () => {
    localStorage.setItem("qwf-lang", "en");
    render(
      <LanguageProvider>
        <Probe />
      </LanguageProvider>
    );
    expect(screen.getByTestId("lang").textContent).toBe("en");
  });

  it("throws if useI18n is used outside a LanguageProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      expect(() => render(<Probe />)).toThrow();
    } finally {
      spy.mockRestore();
    }
  });
});
