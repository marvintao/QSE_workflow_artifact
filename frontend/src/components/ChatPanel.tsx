/**
 * ChatPanel component.
 * Renders the full chat panel: message list, quick-example buttons and the bottom input form.
 */
import { useRef, useState } from "react";
import type { FullTrace } from "../api/types";
import { useI18n } from "../i18n/useI18n";
import type { TranslationKey } from "../i18n/types";
import { ChatMessage, ChatKind } from "./ChatMessage";
import { SolutionCard } from "./SolutionCard";

/** Max input length in characters. The backend RequestPayload.raw_text accepts up to 1_000_000;
 *  the frontend keeps a 5% headroom for i18n and newline fluctuations. */
const MAX_INPUT_CHARS = 950_000;

/** A single chat entry. When `card=true`, the agent message embeds a SolutionCard rendered from the
 *  current trace, so the card content evolves automatically (algorithm -> sub-problems -> exec results
 *  -> verify) as polling advances and more stages arrive. */

/** A single chat entry: `kind` identifies the source, `text` is the verbatim user input (not translated),
 *  `textKey` is the translation key for app-generated messages (re-rendered on language switch), and
 *  `card=true` indicates the message embeds a SolutionCard that renders the current trace and updates
 *  automatically as polling advances. */
export interface ChatEntry {
  kind: ChatKind;
  /** Verbatim user input (not translated). */
  text?: string;
  /** Translation key for an app-generated message (re-rendered when the language switches). */
  textKey?: TranslationKey;
  /** Interpolation variables for the textKey template. */
  textVars?: Record<string, string | number>;
  /** Whether to embed a SolutionCard that evolves with the current trace inside this bubble. */
  card?: boolean;
}

/** Props for ChatPanel: `messages` is the message history, `loading` toggles the loading animation,
 *  `onSubmit` receives user submissions, and `currentTrace` is the current trace snapshot used to
 *  render the SolutionCard inside any message with `card=true`.
 *  Model selection is driven by backend/config; there is no model prop because users no longer pick one. */
export interface ChatPanelProps {
  messages: ChatEntry[];
  loading: boolean;
  onSubmit: (text: string) => void;
  currentTrace?: FullTrace | null;
}

/** Translation keys for quick-example buttons; clicking one fills the input with the translated text, lowering the barrier to entry. */
const QUICK_EXAMPLES: TranslationKey[] = [
  "chat.example1",
  "chat.example2",
  "chat.example3",
  "chat.example4",
];

/**
 * Chat panel component.
 * Owns the input textarea state and passes user input upward via onSubmit.
 * Enter (without Shift) submits; the textarea and button are disabled while loading.
 */
export function ChatPanel({
  messages, loading, onSubmit, currentTrace,
}: ChatPanelProps) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  /** Local submit handler: ignore empty input and loading state; after submit, clear the textarea and file label. */
  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || loading) return;
    onSubmit(trimmed);
    setValue("");
    setFileName(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  /** File-selection handler: read txt/md contents into the input.
   *  Supports .txt / .md / .json; large files are read in one shot; anything beyond MAX_INPUT_CHARS is truncated with a notice. */
  const onFileSelected = async (file: File) => {
    try {
      const text = await file.text();
      if (text.length > MAX_INPUT_CHARS) {
        setValue(text.slice(0, MAX_INPUT_CHARS));
        setFileName(`${file.name} (${file.size} bytes — truncated to ${MAX_INPUT_CHARS} chars)`);
      } else {
        setValue(text);
        setFileName(`${file.name} (${file.size} bytes)`);
      }
    } catch (e) {
      setFileName(`failed to read: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-3.5 overflow-y-auto bg-white p-[18px]">
        {messages.map((m, i) => {
          const resolved = m.textKey ? t(m.textKey, m.textVars) : m.text;
          return (
            <ChatMessage key={i} kind={m.kind} text={resolved}>
              {m.card && currentTrace && <SolutionCard trace={currentTrace} />}
            </ChatMessage>
          );
        })}
        {loading && (
          <div className="flex gap-2.5">
            <div className="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] bg-gradient-to-br from-blue-600 to-cyan-500 text-[15px] text-white shadow-sm">
              🤖
            </div>
            <div className="rounded-xl rounded-bl-sm border border-slate-200 bg-slate-50 px-[14px] py-2.5 text-xs text-slate-600">
              {t("chat.thinking")}
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="border-t border-slate-200 bg-slate-50 p-[18px]"
      >
        <div className="mb-2.5 flex flex-wrap items-center gap-1.5">
          {QUICK_EXAMPLES.map((key, i) => {
            const label = t(key);
            return (
              <button
                key={i}
                type="button"
                data-testid="quick-example"
                onClick={() => setValue(label)}
                className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] text-slate-600 hover:border-blue-600 hover:bg-blue-50 hover:text-blue-600"
              >
                {label.length > 18 ? label.slice(0, 17) + "…" : label}
              </button>
            );
          })}
          {/* Upload a requirement file: paste the full contents into the textarea —
              used for long requirements like req_*.txt that far exceed the 2000-char limit */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.json,text/plain,application/json"
            data-testid="file-upload-input"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFileSelected(f);
            }}
          />
          <button
            type="button"
            data-testid="file-upload-btn"
            disabled={loading}
            onClick={() => fileInputRef.current?.click()}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] text-slate-600 hover:border-blue-600 hover:bg-blue-50 hover:text-blue-600 disabled:opacity-50"
          >
            📎 {t("chat.uploadFile")}
          </button>
          {fileName && (
            <span
              data-testid="file-upload-name"
              className="ml-1 truncate text-[11px] text-slate-500"
              title={fileName}
            >
              {fileName}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            maxLength={MAX_INPUT_CHARS}
            rows={1}
            disabled={loading}
            placeholder={t("chat.placeholder")}
            className="min-h-[44px] flex-1 resize-none rounded-[10px] border-[1.5px] border-slate-300 bg-white px-[14px] py-2.5 text-[13px] text-slate-900 outline-none placeholder:text-slate-500 focus:border-blue-600 disabled:opacity-60"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button
            type="submit"
            disabled={loading || value.trim().length === 0}
            className="whitespace-nowrap rounded-[10px] bg-blue-600 px-5 py-2.5 text-[13px] font-bold text-white shadow hover:bg-blue-700 disabled:bg-slate-300 disabled:text-slate-500 disabled:shadow-none"
          >
            {loading ? t("chat.sending") : t("chat.send")}
          </button>
        </div>
      </form>
    </div>
  );
}
