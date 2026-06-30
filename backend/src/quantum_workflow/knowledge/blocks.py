"""Access to validated numerical building blocks: load modules from `building_blocks/` as aux files for the sandbox.

Building blocks are data (published exact numerical values), not
algorithms. Stage-4 generated code imports them, and stage-6 classical
cross-checks reuse them.
"""
from pathlib import Path

_BLOCKS_DIR = Path(__file__).resolve().parent / "building_blocks"


def building_block_files() -> dict[str, str]:
    """Return every .py module under building_blocks/ as a filename->contents map, excluding __init__.py."""
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted(_BLOCKS_DIR.glob("*.py"))
            if p.name != "__init__.py"}


def building_block_module_names() -> set[str]:
    """Return the building-block module names (without .py suffix) importable by generated code."""
    return {p.stem for p in _BLOCKS_DIR.glob("*.py")
            if p.name != "__init__.py"}


def building_blocks_api() -> str:
    """Return the building-block API manifest (contents of MANIFEST.md) for injection into codegen prompts."""
    return (_BLOCKS_DIR / "MANIFEST.md").read_text(encoding="utf-8")
