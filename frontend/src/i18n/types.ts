// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

import type { zh } from "./zh";

/** Supported UI / model-output languages. */
export type Lang = "en" | "zh";

/** Union of all valid translation keys, derived from the zh dictionary as the source of truth. */
export type TranslationKey = keyof typeof zh;
