/**
 * HTTP API client module.
 * Wraps all fetch calls against the backend /api endpoints, centralizing error handling and JSON parsing.
 */
import type {
  CreateRequestPayload,
  CreateRequestResponse,
  FullTrace,
  RequestSummary,
} from "./types";
import type { Lang } from "../i18n/types";

const BASE_URL = "/api";

/**
 * Shared response handler: on non-2xx responses, prefer body.detail as the error message;
 * if JSON parsing fails, fall back to the HTTP status code string, then throw a unified Error.
 */
async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* swallow JSON parse errors; fall back to status-only message */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

/** Public API client object exposing all backend endpoint methods. */
export const apiClient = {
  /** Create a new quantum workflow request from raw natural-language text + the current UI language.
   *  Model selection is driven entirely by backend/config; the frontend no longer sends a model field. */
  async createRequest(
    rawText: string, language: Lang,
  ): Promise<CreateRequestResponse> {
    const body: CreateRequestPayload = { raw_text: rawText, language };
    const resp = await fetch(`${BASE_URL}/request`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    return handle<CreateRequestResponse>(resp);
  },

  /** Fetch a request summary by requestId, including the final status and the raw input text. */
  async getRequest(requestId: string): Promise<RequestSummary> {
    const resp = await fetch(`${BASE_URL}/request/${requestId}`);
    return handle<RequestSummary>(resp);
  },

  /** Fetch the full execution trace, including the detailed record of every pipeline stage. */
  async getTrace(requestId: string): Promise<FullTrace> {
    const resp = await fetch(`${BASE_URL}/trace/${requestId}`);
    return handle<FullTrace>(resp);
  },
};
