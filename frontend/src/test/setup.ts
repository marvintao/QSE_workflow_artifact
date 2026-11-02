// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * Vitest global test environment setup.
 *
 * Responsibilities:
 *   - Extend jest-dom assertions (toBeInTheDocument, etc.).
 *   - Configure @testing-library/react's default ignore rule to exclude <pre> blocks from text-based assertions.
 *   - Manage the MSW server lifecycle: start before each suite, reset after each test, close after all tests.
 *   - Inject a ResizeObserver polyfill for the jsdom environment to resolve @xyflow/react compatibility issues.
 *   - Override globalThis.localStorage to mask the ERR_INVALID_STATE thrown by Node 25's native implementation
 *     when no --localstorage-file is provided.
 */
import "@testing-library/jest-dom";
import { configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./server";

// Node 25 exposes a native localStorage (backed by SQLite) on globalThis whose access
// requires --localstorage-file to point at a valid database path. Vitest does not pass
// that flag when spawning workers, so any read/write of globalThis.localStorage throws
// ERR_INVALID_STATE. Override the property with a pure in-memory implementation so that
// localStorage operations in tests work as expected.
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = String(value); },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
    key: (index: number) => Object.keys(store)[index] ?? null,
    get length() { return Object.keys(store).length; },
  };
})();
Object.defineProperty(globalThis, "localStorage", {
  value: localStorageMock,
  writable: true,
  configurable: true,
});

// Exclude <pre> blocks (raw JSON payloads in JsonBlock) from getByText queries
// so collapsible details content doesn't pollute text-based assertions.
configure({ defaultIgnore: "script, style, pre" });

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// jsdom polyfill for @xyflow/react
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
