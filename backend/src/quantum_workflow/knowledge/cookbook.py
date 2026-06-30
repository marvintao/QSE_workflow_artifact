"""Qiskit 2.x API usage snippets: algorithm-agnostic library-API call examples.

Injected into stage-4 codegen prompts to correct outdated API
conventions baked into the LLM's training. The contents only cover
library API (how to use StatevectorEstimator, how to bind ansatz
parameters, etc.) and never algorithm structure — algorithm design
remains the LLM's job.
"""
from pathlib import Path

_DOC = Path(__file__).resolve().parent / "qiskit_cookbook.md"


def qiskit_cookbook() -> str:
    """Return the Qiskit 2.x API cookbook for injection into codegen prompts."""
    return _DOC.read_text(encoding="utf-8")
