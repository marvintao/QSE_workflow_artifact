// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * useTrace hook.
 *
 * Watches `requestId` and automatically fetches the corresponding full pipeline trace,
 * polling until the pipeline reaches a terminal state.
 *
 * Behavior:
 *  - requestId = null -> idle.
 *  - When requestId changes, GET once immediately; trace enters "loading" (or "running" after
 *    the first successful response).
 *  - While the pipeline is running (`request.final_status === null`), re-GET every ~700ms so the
 *    UI incrementally sees each stage complete.
 *  - On terminal state (`final_status` in {success, failed}) -> status="success", polling stops.
 *  - On fetch failure (network / 404) -> status="error", polling stops.
 *  - On unmount or requestId change -> cleanup cancels the next poll and discards stale callbacks.
 */
import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { FullTrace } from "../api/types";

/** Lifecycle status of trace fetching: idle / loading (first response pending) / running (polling, some stages already visible) / success (terminal) / error. */
export type TraceStatus = "idle" | "loading" | "running" | "success" | "error";

/** Return type of useTrace: fetch status, the full trace, and an error message. */
export interface UseTraceState {
  status: TraceStatus;
  trace: FullTrace | null;
  error: string | null;
}

/** Polling interval (ms) while the pipeline is running. Tunable: smaller = more "real-time", larger = less network traffic. */
const POLL_INTERVAL_MS = 700;

/**
 * Asynchronously fetch the full trace for a requestId; keep polling until terminal.
 *
 * State machine: idle -> loading -> (running <-> running) -> success | error
 *   - loading: the first response has not yet returned.
 *   - running: at least one trace received, but final_status is still null.
 *   - success: final_status has settled (whether cross_checked or failed).
 *   - error:   the GET failed.
 */
export function useTrace(requestId: string | null): UseTraceState {
  const [status, setStatus] = useState<TraceStatus>(requestId ? "loading" : "idle");
  const [trace, setTrace] = useState<FullTrace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!requestId) {
      setStatus("idle");
      setTrace(null);
      setError(null);
      return;
    }
    // `cancelled` guards against stale async callbacks mutating state after unmount or requestId change
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    setStatus("loading");
    setTrace(null);
    setError(null);

    const tick = () => {
      apiClient
        .getTrace(requestId)
        .then((t) => {
          if (cancelled) return;
          setTrace(t);
          const finished = t.request.final_status !== null;
          setStatus(finished ? "success" : "running");
          if (!finished) {
            timer = setTimeout(tick, POLL_INTERVAL_MS);
          }
        })
        .catch((e: unknown) => {
          if (cancelled) return;
          setError(e instanceof Error ? e.message : String(e));
          setStatus("error");
        });
    };
    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [requestId]);

  return { status, trace, error };
}
