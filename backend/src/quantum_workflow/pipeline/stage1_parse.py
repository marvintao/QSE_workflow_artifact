# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""
Pipeline stage 1: parse.

Input: user-provided raw natural-language text (raw_text).
Output: a structured ParsedIntent.

Calls the LLM to convert an unstructured request into the canonical
JSON representation of a quantum-application intent. Validation and
retry ensure downstream stages receive well-formed structured data.

After the LLM call, a Python fallback scans raw_text for JSON-array
sizes and "id"-field counts and injects them into data_scale_hints —
this guards against the LLM under-counting instance items when faced
with a 143 KB blob, which would otherwise leave analyze with empty
data_scale_hints and force it to guess the problem scale.
"""
import json
import re
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader

from quantum_workflow.llm.retry import call_with_validation
from quantum_workflow.pipeline.language import LANGUAGE_NAMES
from quantum_workflow.schemas.intent import ParsedIntent


def _scan_json_arrays(raw_text: str) -> list[list]:
    """Scan raw_text and collect **every** balanced JSON-array block via json.JSONDecoder.raw_decode.

    Typical req_* cases have 1-2 sections (features list + constraints
    list). The older "first [ to last ]" heuristic swallowed the
    intermediate text between sections and broke parsing.

    For each `[` encountered, try to raw_decode from that position; on
    success, record the array and skip past it; on failure, advance one
    character and try again. Only lists are collected (objects `{...}`
    are ignored).
    """
    arrays: list[list] = []
    decoder = json.JSONDecoder()
    i = 0
    n = len(raw_text)
    while i < n:
        c = raw_text[i]
        if c == "[":
            try:
                obj, end = decoder.raw_decode(raw_text, i)
                if isinstance(obj, list) and obj:
                    arrays.append(obj)
                    i = end
                    continue
            except (json.JSONDecodeError, ValueError):
                pass
        i += 1
    return arrays


def _section_label_before(raw_text: str, array_start_token: str) -> str:
    """Guess a label from the nearest non-empty line above the array's first item token (helps disambiguate 'features' / 'constraints' etc. when multiple sections are merged). Falls back to a positional index."""
    # Find the first occurrence of array_start_token in the text, then scan upward for the nearest "title line".
    idx = raw_text.find(array_start_token)
    if idx < 0:
        return ""
    head = raw_text[:idx]
    # Look at non-empty lines within the previous ~800 chars (titles are usually under 80 chars).
    for line in reversed(head[-800:].splitlines()):
        s = line.strip()
        if not s:
            continue
        # Skip pure-punctuation / markdown-decoration lines.
        if all(ch in "-=*#" for ch in s):
            continue
        # Take a colon / data-description line and normalize to a slug.
        slug = re.sub(r"[^a-zA-Z0-9一-鿿_]+", "_", s.lower()).strip("_")
        if slug and len(slug) < 80:
            return slug
        return ""
    return ""


def _extract_instance_data(raw_text: str) -> tuple[int | None, list | dict | None]:
    r"""Extract instance item count + concrete data from raw_text, so analyze knows the scale and the orchestrator can slice data for codegen. Returns (count, data).

    1. Scan every top-level JSON array section:
       - 1 section -> return the list directly.
       - Multiple sections -> merge into a dict whose keys come from
         the slug guessed from the nearest title line above each
         section (falling back to `section_<idx>` on conflict / empty
         label); count = total across sections.
    2. 0 sections -> fall back to the `"id"\s*:` heuristic for item
       count; leave data as None.
    """
    arrays = _scan_json_arrays(raw_text)
    if len(arrays) == 1:
        return len(arrays[0]), arrays[0]
    if len(arrays) >= 2:
        merged: dict = {}
        used_labels: set[str] = set()
        for idx, arr in enumerate(arrays):
            # Use a compact JSON string of the array's first item as an anchor to locate the array in the text.
            try:
                anchor = json.dumps(arr[0], ensure_ascii=False)[:40]
            except Exception:  # noqa: BLE001
                anchor = ""
            label = _section_label_before(raw_text, anchor) if anchor else ""
            if (not label) or label in used_labels:
                label = f"section_{idx}"
            used_labels.add(label)
            merged[label] = arr
        return sum(len(a) for a in arrays), merged

    # 0 JSON-array sections: fall back to heuristics.
    id_count = len(re.findall(r'"id"\s*:', raw_text))
    if id_count > 0:
        return id_count, None
    return None, None


def _count_instance_items(raw_text: str) -> int | None:
    """Backwards-compatible thin shim that delegates to _extract_instance_data."""
    n, _ = _extract_instance_data(raw_text)
    return n

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), keep_trailing_newline=True)

_SYSTEM = (
    "You are a quantum-application requirements analyst. "
    "Always respond with strict JSON, no prose."
)


class Stage1Parse:
    """Stage 1: parse raw user text into a structured quantum-application intent."""

    def __init__(self, llm, model_name: str):
        """Initialize the parse stage.

        Args:
            llm: LLM adapter that must implement call_json().
            model_name: Model identifier string written into trace
                metadata for audit.
        """
        self.llm = llm
        self.model_name = model_name

    def run(self, raw_text: str, language: Literal["en", "zh"] = "en") -> tuple[ParsedIntent, dict]:
        """Parse the user's raw request and return the intent plus LLM-call metadata.

        Args:
            raw_text: User natural-language input.
            language: Language code (en/zh) controlling the language
                used for the LLM's natural-language fields; defaults to "en".
        Returns:
            (ParsedIntent, meta_dict) where meta_dict contains
            llm_input/llm_output/tokens/model.
        """
        tmpl = _env.get_template("stage1_parse.jinja")
        user = tmpl.render(raw_text=raw_text, language_name=LANGUAGE_NAMES[language])

        def _llm_call(prompt: str):
            # cache_system=True enables system-prompt caching to cut token usage under high concurrency.
            return self.llm.call_json(system=_SYSTEM, user=prompt,
                                      cache_system=True)

        intent, usage, raws = call_with_validation(
            llm_call=_llm_call,
            validate=lambda raw: ParsedIntent(**raw),
            base_user_prompt=user,
        )
        # Python fallback: extract instance data from raw_text.
        # 1) Count items -> data_scale_hints.item_count so analyze sees the true N.
        # 2) Persist the full data -> intent.instance_data so the
        #    orchestrator can slice it for codegen (each block takes
        #    the matching index range).
        item_count, data = _extract_instance_data(raw_text)
        if item_count is not None:
            existing = intent.data_scale_hints.get("item_count", 0)
            if item_count > existing:
                intent.data_scale_hints["item_count"] = item_count
        if data is not None and intent.instance_data is None:
            intent.instance_data = data

        meta = {
            "llm_input": {"system": _SYSTEM, "user": user},
            "llm_output": {"artifact": intent.model_dump(),
                           "raw_attempts": raws},
            "tokens": usage,
            "model": self.model_name,
        }
        return intent, meta
