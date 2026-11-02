// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

import { describe, it, expect } from "vitest";
import { zh } from "../../src/i18n/zh";
import { en } from "../../src/i18n/en";

describe("i18n dictionaries", () => {
  it("en and zh have exactly the same key set", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(zh).sort());
  });

  it("no dictionary value is empty", () => {
    for (const v of Object.values(zh)) expect(v.length).toBeGreaterThan(0);
    for (const v of Object.values(en)) expect(v.length).toBeGreaterThan(0);
  });

  it("interpolation placeholders match between languages", () => {
    const ph = (s: string) => (s.match(/\{[a-zA-Z]+\}/g) ?? []).sort();
    for (const k of Object.keys(zh) as (keyof typeof zh)[]) {
      expect(ph(en[k])).toEqual(ph(zh[k]));
    }
  });
});
