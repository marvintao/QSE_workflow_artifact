# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Map language codes to human-readable language names used by the LLM.

Pipeline stages call this when rendering prompts to convert the
request's language code (en/zh) into the readable language name
injected into the model prompt.
"""

# Language code -> human-readable name injected into prompts.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "zh": "简体中文",
}
