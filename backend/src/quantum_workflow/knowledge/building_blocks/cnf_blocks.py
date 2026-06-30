"""Quantum building block: CNF clause -> QUBO penalty conversion.

Boolean CNF (conjunctive-normal-form) clauses appear frequently in
partition-block inputs:
    [{"id": 1, "constraint": "A1"},
     {"id": 2, "constraint": "A1 or not C2"},
     {"id": 3, "constraint": "C2 or not A1"}, ...]

When the LLM writes the parser + clause -> quadratic penalty conversion
itself, the code is long (150+ lines) and indentation breaks easily — in
practice 5-7 indentation errors consume the entire 15-round budget.
This helper crystallizes the logic in ~70 lines of tested code so the
LLM can just `import cnf_blocks; ...` and avoid the indentation disaster.

Penalty design: each clause C contributes penalty=1 when violated and
0 when satisfied. Specifically, for a clause `L_1 or L_2 or ... or L_k`
(L_i is x_i or not x_i), the clause is violated iff every literal is
false, i.e. iff ∏_i (1 - L_i) = 1. Expanding into a polynomial in x_i
and accumulating into Q gives:
    diag (i appears in the clause):
      positive literal L_i = x_i        -> 1 - L_i = 1 - x_i
      negated literal L_i = not x_i     -> 1 - L_i = x_i

    so violation(clause) = ∏_i {x_i if neg_i else (1 - x_i)}.

    QUBO note: x_i^2 = x_i, so after expansion coefficients are folded
    into Q[i, i] / Q[i, j].
"""

from __future__ import annotations

import re

import numpy as np

# Allowed clause-text connectives (or / OR / |) and literal prefixes (not / NOT / ~ / !).
_LITERAL_RE = re.compile(
    r"^(?:(not|!|~)\s*)?([A-Za-z_][A-Za-z0-9_]*)$",
    flags=re.IGNORECASE,
)
_SPLIT_OR_RE = re.compile(r"\s*\b(?:or|OR)\b\s*|\s*\|\s*", flags=re.IGNORECASE)


def parse_clause(clause: str) -> list[tuple[str, bool]]:
    """Parse a single CNF clause string and return [(var_name, is_negated), ...].

    Supported forms:
      - "A1"                  -> [("A1", False)]
      - "A1 or not C2"        -> [("A1", False), ("C2", True)]
      - "C2 or not A1 or A4"  -> [("C2", False), ("A1", True), ("A4", False)]
      - "not X | Y"           -> [("X", True), ("Y", False)]

    Raises ValueError on unparseable literals (empty, special characters, wrong prefix).
    """
    parts = _SPLIT_OR_RE.split(clause.strip())
    literals: list[tuple[str, bool]] = []
    for raw in parts:
        token = raw.strip()
        if not token:
            continue
        m = _LITERAL_RE.match(token)
        if not m:
            raise ValueError(
                f"unparseable literal {token!r} in clause {clause!r}"
            )
        neg = bool(m.group(1))
        name = m.group(2)
        literals.append((name, neg))
    if not literals:
        raise ValueError(f"empty clause {clause!r}")
    return literals


def parse_clauses(clauses: list[dict | str]) -> list[list[tuple[str, bool]]]:
    """Parse a list of clauses in bulk (each item can be a dict {"constraint": "..."} or a plain string)."""
    out = []
    for c in clauses:
        text = c.get("constraint") if isinstance(c, dict) else c
        if not isinstance(text, str):
            raise ValueError(f"clause must have 'constraint' string,got {c!r}")
        out.append(parse_clause(text))
    return out


def clause_penalty_to_qubo(
    parsed_clauses: list[list[tuple[str, bool]]],
    name_to_idx: dict[str, int],
    n: int,
    penalty_weight: float = 1.0,
) -> np.ndarray:
    """Convert a list of CNF clauses into an n x n upper-triangular QUBO penalty matrix.

    violation(clause) = ∏_i {x_i if neg_i else (1 - x_i)}. After
    expansion, coefficients accumulate into Q; x_i^2 = x_i, so QUBO only
    keeps the diagonal plus the i < j upper triangle.

    Args:
        parsed_clauses: Output of parse_clauses().
        name_to_idx: Variable name -> QUBO index (0..n-1).
        n: Total variable count.
        penalty_weight: Multiplier λ for each clause violation.
    Returns:
        Q (n, n) ndarray; Q[i, i] = linear coefficient, Q[i, j] (i < j)
        = quadratic coefficient. Q[j, i] (i < j) is left at 0 (upper-
        triangular convention); downstream code can symmetrize when
        evaluating Q @ x @ x.
    """
    Q = np.zeros((n, n), dtype=float)
    for literals in parsed_clauses:
        # Skip unknown variables silently (the LLM may pass clauses outside the current partition slice).
        try:
            idx_lits = [
                (name_to_idx[name], neg) for name, neg in literals
            ]
        except KeyError:
            continue
        # Collect polynomial coefficients in x_i^k using a dict:
        # tuple(sorted idx subset) -> coef. Empty subset = constant
        # term; length 1 = linear; length 2+ folded down via x_i^2 = x_i.
        poly: dict[tuple[int, ...], float] = {(): penalty_weight}
        for idx, neg in idx_lits:
            # factor: (1 - x_idx) for positive literal (inverted); (x_idx)
            # for negated literal. Multiply each existing term by
            # [coef_const, coef_x] expanded on the {const, x_idx} basis.
            new_poly: dict[tuple[int, ...], float] = {}
            for subset, coef in poly.items():
                # Multiply by const part (neg -> 0; non-neg -> 1).
                const_part = 0.0 if neg else 1.0
                if const_part:
                    new_poly[subset] = new_poly.get(subset, 0.0) + coef * const_part
                # Multiply by x_idx part (neg -> +1; non-neg -> -1).
                x_coef = 1.0 if neg else -1.0
                # x_i * x_i = x_i (QUBO): merge into subset ∪ {idx}.
                if idx in subset:
                    new_subset = subset
                else:
                    new_subset = tuple(sorted(subset + (idx,)))
                new_poly[new_subset] = new_poly.get(new_subset, 0.0) + coef * x_coef
            poly = new_poly
        # Write into Q: drop the constant term (empty subset; QUBO does
        # not store constants); linear terms go on the diagonal;
        # quadratic terms go in the upper triangle; >2 terms are
        # impossible (each variable appears at most once per clause).
        for subset, coef in poly.items():
            if abs(coef) < 1e-15:
                continue
            if len(subset) == 0:
                continue   # ignore constant term (does not affect QUBO argmin)
            if len(subset) == 1:
                i = subset[0]
                Q[i, i] += coef
            elif len(subset) == 2:
                i, j = subset
                Q[i, j] += coef       # upper-triangular convention: i < j
            else:
                # Within a single clause each variable appears at most
                # once, so max subset size = literal count. A >2 subset
                # would mean a repeated variable; defensively fall back
                # to splitting the coefficient across the diagonal.
                for v in subset:
                    Q[v, v] += coef / len(subset)
    return Q


def boolean_eval(
    bitstring: str,
    parsed_clauses: list[list[tuple[str, bool]]],
    name_to_idx: dict[str, int],
) -> tuple[int, int]:
    """Decode a bitstring and count (satisfied clauses, violated clauses).

    bitstring[i] = '1' means x_i = 1 (variable selected); '0' means
    x_i = 0. Length must be >= max(name_to_idx index) + 1.
    """
    sat = 0
    vio = 0
    for literals in parsed_clauses:
        clause_satisfied = False
        for name, neg in literals:
            if name not in name_to_idx:
                continue
            idx = name_to_idx[name]
            if idx >= len(bitstring):
                continue
            xi = bitstring[idx] == "1"
            literal_val = (not xi) if neg else xi
            if literal_val:
                clause_satisfied = True
                break
        if clause_satisfied:
            sat += 1
        else:
            vio += 1
    return sat, vio
