// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * useRequest hook.
 * Wraps the async state machine for submitting a quantum workflow request to the backend,
 * exposing `submit` / `reset` operations along with the current state.
 */
import { useState } from "react";
import { apiClient } from "../api/client";
import type { Lang } from "../i18n/types";

/** Request lifecycle status: idle -> loading -> success / error. */
export type RequestStatus = "idle" | "loading" | "success" | "error";

/** Return type of the useRequest hook: status fields plus submit / reset operations. */
export interface UseRequestState {
  status: RequestStatus;
  requestId: string | null;
  error: string | null;
  submit: (rawText: string, language: Lang) => Promise<void>;
  reset: () => void;
}

/**
 * Manages the async state of a quantum workflow request.
 * Returns `status` (request lifecycle), `requestId` (backend-assigned ID), `error`, and the
 * `submit` / `reset` methods.
 * Model selection is driven entirely by backend/config; `submit` does not accept a model parameter.
 */
export function useRequest(): UseRequestState {
  const [status, setStatus] = useState<RequestStatus>("idle");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Submit a request: reset prior state, then call the API with `language` (the UI language). */
  const submit = async (rawText: string, language: Lang) => {
    setStatus("loading");
    setError(null);
    setRequestId(null);
    try {
      const { request_id } = await apiClient.createRequest(rawText, language);
      setRequestId(request_id);
      setStatus("success");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus("error");
    }
  };

  /** Reset all state to initial values; invoked when the conversation is reset. */
  const reset = () => {
    setStatus("idle");
    setRequestId(null);
    setError(null);
  };

  return { status, requestId, error, submit, reset };
}
