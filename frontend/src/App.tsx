// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * Root component responsible for the overall layout and cross-panel state coordination.
 * Composes the chat panel, workflow visualizer and detail inspector into a three-column layout,
 * driving the data flow through the useRequest / useTrace hooks.
 */
import { useEffect, useRef, useState } from "react";
import { ChatPanel, type ChatEntry } from "./components/ChatPanel";
import { DetailInspector, type Selected } from "./components/DetailInspector";
import { LanguageSelector } from "./components/LanguageSelector";
import { VerificationBadge } from "./components/VerificationBadge";
import { WorkflowPanel } from "./components/WorkflowPanel";
import type { TraceEventRef } from "./components/TraceTimeline";
import { useI18n } from "./i18n/useI18n";
import { useRequest } from "./hooks/useRequest";
import { useTrace } from "./hooks/useTrace";

/** Initial greeting message shown as the first chat entry after every reset. */
const GREETING: ChatEntry = {
  kind: "agent",
  textKey: "chat.greeting",
};

/**
 * App root component.
 * Manages the message list, the selected detail target and request/trace state,
 * and coordinates interactions across the three main panels.
 */
export default function App() {
  const { t, lang } = useI18n();
  const req = useRequest();
  const trace = useTrace(req.requestId);
  const [messages, setMessages] = useState<ChatEntry[]>([GREETING]);
  const [selected, setSelected] = useState<Selected>(null);
  // The handled ref deduplicates chat appends — each hook keyed entry is added once.
  // ok/err: terminal-state messages; announced: per-stage intermediate (rid + key) dedup set.
  const handled = useRef<{
    ok: string | null;
    err: string | null;
    announced: Set<string>;
  }>({ ok: null, err: null, announced: new Set() });

  /** Submit user input: append the user message and trigger the backend request. Model selection is driven by backend/config. */
  const submit = (text: string) => {
    setMessages((m) => [...m, { kind: "user", text }]);
    req.submit(text, lang);
  };

  // While the pipeline is running, append per-stage intermediate updates to the chat (each key once).
  // This surfaces milestones such as "algorithm locked", "N sub-problems planned", "sub-problem #N solved".
  useEffect(() => {
    const tr = trace.trace;
    if (!tr) return;
    const rid = tr.request.request_id;
    const announce = (key: string, entry: ChatEntry) => {
      const dedupKey = `${rid}:${key}`;
      if (handled.current.announced.has(dedupKey)) return;
      handled.current.announced.add(dedupKey);
      setMessages((m) => [...m, entry]);
    };

    // analyze done -> append an agent message that embeds a "solution card".
    // The card renders the current trace; as polling advances it automatically evolves from
    // "algorithm + sub-problems" to "with execution results", so the same message is appended only once.
    const analyze = tr.stages.find((s) => s.stage === "analyze");
    if (analyze && analyze.artifact) {
      announce("opportunity", {
        kind: "agent", textKey: "chat.opportunityReady", card: true,
      });
    }

    // encode done -> announce the decomposition strategy + number of sub-problems
    const encode = tr.stages.find((s) => s.stage === "encode");
    const encodeArt = encode?.artifact as
      | { strategy?: string; sub_problems?: unknown[] }
      | undefined;
    if (encode && encodeArt?.sub_problems) {
      announce("encode", {
        kind: "agent", textKey: "chat.encodingPlanned",
        textVars: {
          n: encodeArt.sub_problems.length,
          strategy: encodeArt.strategy ?? "",
        },
      });
    }

    // Each successful execute attempt -> announce that sub-problem's result
    for (const s of tr.stages) {
      if (s.stage !== "execute") continue;
      const art = s.artifact as
        | { status?: string; result?: { value?: number | string } }
        | undefined;
      if (art?.status === "success") {
        const v = art.result?.value;
        announce(`exec:${s.attempt}`, {
          kind: "agent", textKey: "chat.executeOk",
          textVars: { idx: s.attempt, value: v ?? "—" },
        });
      }
    }
  }, [trace.trace]);

  // On pipeline terminal state: use request_id as the idempotency key to append a success or failure message exactly once.
  useEffect(() => {
    if (trace.status !== "success" || !trace.trace) return;
    const rid = trace.trace.request.request_id;
    if (handled.current.ok === rid) return;
    handled.current.ok = rid;
    const traceData = trace.trace;
    const isSuccess = traceData.request.final_status === "success";
    // At terminal state: the solution card was already inserted on analyze completion and has
    // evolved with polling, so we do not insert another card here. Just append a short text
    // delivering the final verdict to the user.
    // On failure, pick the last stage carrying error_type to surface "which stage failed and why",
    // avoiding a generic "pipeline failed: failed".
    let entry: ChatEntry;
    if (isSuccess) {
      entry = { kind: "agent", textKey: "chat.solutionReady" };
    } else {
      const failedStage = [...traceData.stages].reverse().find(
        (s) => (s.artifact as Record<string, unknown> | null)?.error_type,
      );
      if (failedStage) {
        const a = failedStage.artifact as Record<string, unknown>;
        // error_chain carries the __cause__ chain (revealing the true root cause beneath SDK
        // wrappers, e.g. "APIConnectionError: Connection error. -> RemoteProtocolError:
        // Server disconnected ..."); prefer it, falling back to error_message.
        const detail = (a.error_chain as string)
                      ?? (a.error_message as string) ?? "";
        entry = {
          kind: "system", textKey: "chat.pipelineFailedAtStage",
          textVars: {
            stage: failedStage.stage,
            errorType: String(a.error_type),
            errorMessage: detail,
          },
        };
      } else {
        entry = {
          kind: "system", textKey: "chat.pipelineFailed",
          textVars: {
            error: traceData.request.verification_status ?? "failed",
          },
        };
      }
    }
    setMessages((m) => [...m, entry]);
  }, [trace.status, trace.trace]);

  // The POST itself errored (rare — background pipeline failures do not fail the POST) -> append an error message
  useEffect(() => {
    if (
      req.status === "error" &&
      req.error &&
      handled.current.err !== req.error
    ) {
      handled.current.err = req.error;
      const errorMsg = req.error;
      setMessages((m) => [
        ...m,
        { kind: "system", textKey: "chat.pipelineFailed", textVars: { error: errorMsg } },
      ]);
    }
  }, [req.status, req.error]);

  /** Reset the conversation: restore the greeting, clear request state and dedup records. */
  const reset = () => {
    setMessages([GREETING]);
    req.reset();
    setSelected(null);
    // Clear the handled ref in sync so the next request can correctly trigger message appends
    handled.current = { ok: null, err: null, announced: new Set() };
  };

  // Show loading whenever any async stage is in flight: POST pending, first trace not yet arrived, or pipeline still running
  const loading =
    req.status === "loading" ||
    trace.status === "loading" ||
    trace.status === "running";
  // As long as a trace exists (running or success), pass it to the view layer so intermediate progress is visible
  const fullTrace = trace.trace;
  const hasTrace = fullTrace !== null;
  // Narrow the Selected union to a TraceEventRef, used to drive timeline highlighting
  const selectedEventId: TraceEventRef | null =
    selected?.kind === "event" ? selected.ref : null;

  return (
    <div
      className="grid h-screen bg-slate-50 text-slate-900"
      style={{
        // Use minmax(0, 1fr) instead of 1fr: with grid's default min-width=auto, long
        // inner content (code blocks / SVG / long Hamiltonian strings) would expand the
        // middle column and squeeze the adjacent fixed columns. minmax(0, 1fr) lets the
        // middle column shrink to 0, so the fixed side columns are no longer affected by
        // the middle column's content width.
        gridTemplateColumns: hasTrace
          ? "420px minmax(0, 1fr) 360px"
          : "460px minmax(0, 1fr)",
        gridTemplateRows: "60px 1fr",
      }}
    >
      <header
        className="flex items-center justify-between border-b border-slate-200 bg-white px-6 shadow-sm"
        style={{ gridColumn: "1 / -1" }}
      >
        <h1 className="flex items-center gap-2.5 text-base font-bold text-slate-900">
          <span className="flex h-[30px] w-[30px] items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-cyan-500 text-base text-white shadow">
            ⚛
          </span>
          {t("app.title")}
          <span className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700">
            {t("app.badge")}
          </span>
        </h1>
        <div className="flex items-center gap-2">
          <LanguageSelector />
          <button
            type="button"
            onClick={reset}
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:border-blue-100 hover:bg-blue-50 hover:text-blue-600"
          >
            {t("app.reset")}
          </button>
        </div>
      </header>

      <aside className="flex min-h-0 min-w-0 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-[18px] py-3.5 text-[13px] font-bold text-slate-600">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          {t("app.chatHeader")}
        </div>
        <ChatPanel
          messages={messages}
          loading={loading}
          onSubmit={submit}
          currentTrace={fullTrace}
        />
      </aside>

      <main className="flex min-h-0 min-w-0 flex-col bg-slate-50">
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-[18px] py-3.5">
          <h3 className="text-[13px] font-bold text-slate-600">{t("app.workflowHeader")}</h3>
          {fullTrace && (
            <div className="flex items-center gap-1.5 text-[11px]">
              <VerificationBadge
                status={fullTrace.request.verification_status}
              />
              <span className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-0.5 font-bold text-blue-700">
                {t("app.stageRows", { count: fullTrace.stages.length })}
              </span>
            </div>
          )}
        </div>
        <WorkflowPanel
          trace={fullTrace}
          onSelectNode={(id) => setSelected({ kind: "node", id })}
          onSelectEvent={(ref) => setSelected({ kind: "event", ref })}
          selectedEventId={selectedEventId}
        />
      </main>

      {hasTrace && fullTrace && (
        <section className="flex min-h-0 min-w-0 flex-col border-l border-slate-200 bg-white">
          <DetailInspector
            trace={fullTrace}
            selected={selected}
            onClose={() => setSelected(null)}
          />
        </section>
      )}
    </div>
  );
}
