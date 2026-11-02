// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * MSW test server instance.
 *
 * Registers all handlers with the Node.js-side MSW server.
 * Its lifecycle is centrally managed by setup.ts (beforeAll start / afterEach reset / afterAll close).
 */
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/** Exported MSW server instance — setup.ts drives it uniformly across all test suites. */
export const server = setupServer(...handlers);
