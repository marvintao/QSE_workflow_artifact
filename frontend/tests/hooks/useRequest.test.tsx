// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useRequest } from "../../src/hooks/useRequest";

describe("useRequest", () => {
  it("starts idle, transitions through loading to success", async () => {
    const { result } = renderHook(() => useRequest());
    expect(result.current.status).toBe("idle");
    expect(result.current.requestId).toBeNull();

    await act(async () => {
      await result.current.submit("Find H2 ground state", "en");
    });

    expect(result.current.status).toBe("success");
    expect(result.current.requestId).toBe("test-rid-1");
    expect(result.current.error).toBeNull();
  });

  it("captures errors when backend fails", async () => {
    const { result } = renderHook(() => useRequest());
    await act(async () => {
      await result.current.submit("FAIL", "en");
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/pipeline failed/);
    expect(result.current.requestId).toBeNull();
  });

  it("clears error state on a new submission", async () => {
    const { result } = renderHook(() => useRequest());

    await act(async () => {
      await result.current.submit("FAIL", "en");
    });
    expect(result.current.status).toBe("error");
    expect(result.current.error).not.toBeNull();

    await act(async () => {
      await result.current.submit("Find H2 ground state", "en");
    });
    expect(result.current.status).toBe("success");
    expect(result.current.error).toBeNull();
    expect(result.current.requestId).toBe("test-rid-1");
  });

  it("loading state is reachable via waitFor before resolution", async () => {
    const { result } = renderHook(() => useRequest());

    let p: Promise<void>;
    act(() => {
      p = result.current.submit("Find H2 ground state", "en");
    });
    // Inside the synchronous portion of submit, status should be loading.
    expect(result.current.status).toBe("loading");
    expect(result.current.requestId).toBeNull();

    await act(async () => {
      await p;
    });
    expect(result.current.status).toBe("success");
  });

  it("submits and stores returned request_id (model is config-driven)", async () => {
    // submit only takes rawText + language; model is chosen by backend/config,
    // never sent from the frontend.
    const { result } = renderHook(() => useRequest());
    await act(async () => {
      await result.current.submit("hello", "zh");
    });
    expect(result.current.status).toBe("success");
    expect(result.current.requestId).toBe("test-rid-1");
  });
});
