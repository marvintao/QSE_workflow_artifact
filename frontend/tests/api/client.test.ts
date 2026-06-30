import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../../src/test/server";
import { apiClient } from "../../src/api/client";

describe("apiClient", () => {
  it("submits a request and returns request_id", async () => {
    const result = await apiClient.createRequest("Find H2 ground state", "en");
    expect(result.request_id).toBe("test-rid-1");
  });

  it("fetches request status", async () => {
    const r = await apiClient.getRequest("test-rid-1");
    expect(r.final_status).toBe("success");
    expect(r.raw_text).toBe("Find H2 ground state");
  });

  it("fetches full trace", async () => {
    const trace = await apiClient.getTrace("test-rid-1");
    expect(trace.stages.length).toBe(8);
    expect(trace.request.verification_status).toBe("cross_checked");
    const exec = trace.stages.find((s) => s.stage === "execute");
    expect(
      (exec?.artifact?.result as Record<string, number> | undefined)
        ?.value,
    ).toBeCloseTo(-1.137, 2);
  });

  it("throws on 4xx with detail", async () => {
    await expect(apiClient.getTrace("missing")).rejects.toThrow(
      /request not found/
    );
  });

  it("throws on 502 StageError with pipeline message", async () => {
    await expect(apiClient.createRequest("FAIL", "en")).rejects.toThrow(
      /pipeline failed/
    );
  });

  it("never sends a model field (model is config-driven)", async () => {
    let captured: any = null;
    server.use(
      http.post("/api/request", async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({ request_id: "ok-rid" });
      }),
    );
    await apiClient.createRequest("hello", "zh");
    expect(captured.raw_text).toBe("hello");
    expect(captured.language).toBe("zh");
    expect("model" in captured).toBe(false);
  });
});
