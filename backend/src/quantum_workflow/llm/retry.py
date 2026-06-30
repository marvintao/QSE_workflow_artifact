"""Retry helper: validate the LLM result and, on failure, retry once with the error attached."""

from collections.abc import Callable
from typing import TypeVar

from .protocol import LLMError

T = TypeVar("T")


def call_with_validation(
    *,
    llm_call: Callable[[str], tuple[dict, dict]],
    validate: Callable[[dict], T],
    base_user_prompt: str,
) -> tuple[T, dict, list[dict]]:
    """Call the LLM, validate the JSON result, and retry once with the error attached on failure.

    Args:
        llm_call: Callable that takes the user-prompt string and returns
            (raw JSON dict, usage dict).
        validate: Callable that takes the raw dict and returns a parsed
            object, raising when the data is invalid.
        base_user_prompt: Initial user prompt.
    Returns:
        (validated object, usage dict of the successful call, list of all raw outputs).
    Raises:
        LLMError: Raised when both attempts fail validation.
    """
    raw_outputs: list[dict] = []

    raw, usage = llm_call(base_user_prompt)
    raw_outputs.append(raw)
    try:
        return validate(raw), usage, raw_outputs
    except Exception as first_err:  # noqa: BLE001 - corrective-retry envelope
        # Append the first validation error to the prompt and ask the model for corrected JSON.
        correction = (
            f"{base_user_prompt}\n\n"
            f"Your previous response failed validation with this error:\n"
            f"{first_err}\n"
            f"Return corrected strict JSON only."
        )
        raw2, usage2 = llm_call(correction)
        raw_outputs.append(raw2)
        try:
            return validate(raw2), usage2, raw_outputs
        except Exception as second_err:  # noqa: BLE001
            raise LLMError(
                f"LLM output failed validation twice: {second_err}"
            ) from second_err
