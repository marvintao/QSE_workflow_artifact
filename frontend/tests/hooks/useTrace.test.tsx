import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { useTrace } from "../../src/hooks/useTrace";
import { server } from "../../src/test/server";
import { fakeFullTrace } from "../../src/test/handlers";

describe("useTrace", () => {
  it("loads trace data given a request id", async () => {
    const { result } = renderHook(() => useTrace("test-rid-1"));
    expect(result.current.status).toBe("loading");
    expect(result.current.trace).toBeNull();

    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.trace?.stages.length).toBe(8);
    const exec = result.current.trace?.stages.find((s) => s.stage === "execute");
    expect(
      (exec?.artifact?.result as Record<string, number> | undefined)
        ?.value,
    ).toBeCloseTo(-1.137, 2);
  });

  it("handles null requestId gracefully", () => {
    const { result } = renderHook(() => useTrace(null));
    expect(result.current.status).toBe("idle");
    expect(result.current.trace).toBeNull();
  });

  it("captures 404 error", async () => {
    const { result } = renderHook(() => useTrace("missing"));
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error).toMatch(/request not found/);
  });

  it("polls while pipeline still running and stops at terminal state", async () => {
    // MSW handler: first 2 calls return an "in-flight" trace (final_status=null,
    // stages growing); the 3rd returns the terminal state. useTrace should go
    // loading → running → success while stages count grows.
    let n = 0;
    server.use(
      http.get("/api/trace/poll-rid", () => {
        n += 1;
        if (n === 1) {
          return HttpResponse.json({
            request: { ...fakeFullTrace.request, request_id: "poll-rid",
                       final_status: null, verification_status: null },
            stages: fakeFullTrace.stages.slice(0, 2),
          });
        }
        if (n === 2) {
          return HttpResponse.json({
            request: { ...fakeFullTrace.request, request_id: "poll-rid",
                       final_status: null, verification_status: null },
            stages: fakeFullTrace.stages.slice(0, 5),
          });
        }
        return HttpResponse.json({
          ...fakeFullTrace,
          request: { ...fakeFullTrace.request, request_id: "poll-rid" },
        });
      }),
    );
    const { result } = renderHook(() => useTrace("poll-rid"));
    // First reaches running (got the first trace but final_status not yet set).
    await waitFor(() => expect(result.current.status).toBe("running"));
    expect(result.current.trace?.stages.length).toBe(2);
    // Wait for terminal state (success): polling picks up final_status=success.
    await waitFor(() => expect(result.current.status).toBe("success"),
                   { timeout: 5000 });
    expect(result.current.trace?.stages.length).toBe(8);
    expect(n).toBeGreaterThanOrEqual(3);  // At least 3 GETs (2 running + 1 terminal).
  });
});
