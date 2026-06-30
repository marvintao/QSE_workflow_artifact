# This script processes the original configuration optimization benchmarks to
# create JSON files containing reproduced feature costs and CNF constraints.

import json
import os
import re

import numpy as np

DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_DIR = os.path.join(DIRECTORY, "original", "config_opt")
JSON_DIR = os.path.join(DIRECTORY, "json")

MIN_FEATURE_COST = 10
MAX_FEATURE_COST = 100
RANDOM_SEED = 42
FEATURE_MODEL_PATTERN = re.compile(r"feature_model_(\d+)\.dimacs$")


class DimacsReader:
    """Reader compatible with the source project's DIMACS benchmark format."""

    def __init__(self) -> None:
        self.features: dict[int, str] = {}
        self.attributeMap: list[tuple[str, int, float]] = []
        self.nFeatures = 0
        self.nClauses = 0
        self.clauses: list[list[int]] = []

    def fromFile(self, path: str) -> None:
        id_comment = re.compile(r"c\s*(\d+)\s*(\w+)\s*")
        attr_comment = re.compile(r"c\s*attr\s*(\w+)\s*(\d+)\s*(-?[0-9]\d*(\.\d+)?)\s*")
        clauses = re.compile(r"p\s*cnf\s*(\d+)\s*(\d+)")

        with open(path, "r", encoding="utf-8") as dimacs_file:
            lines = [line.rstrip() for line in dimacs_file]

        while lines:
            line = lines.pop(0)
            match = id_comment.match(line)
            if match:
                feature_id = int(match.group(1))
                name = match.group(2)
                self.features[feature_id] = name
                continue

            match = attr_comment.match(line)
            if match:
                name = match.group(1)
                feature_id = int(match.group(2))
                value = float(match.group(3))
                self.attributeMap.append((name, feature_id, value))
                continue

            match = clauses.match(line)
            if match:
                self.nFeatures = int(match.group(1))
                self.nClauses = int(match.group(2))
                self.clauses = [list(map(int, clause_line.split())) for clause_line in lines if clause_line]
                break


def feature_model_index(path: str) -> int:
    filename = os.path.basename(path)
    match = FEATURE_MODEL_PATTERN.match(filename)
    if match is None:
        raise ValueError(f"Unexpected feature model filename: {filename}")
    return int(match.group(1))


def get_feature_model_paths() -> list[str]:
    """Return feature_model_<index>.dimacs files in the same order as the source project."""
    return sorted(
        [
            os.path.join(ORIGINAL_DIR, filename)
            for filename in os.listdir(ORIGINAL_DIR)
            if FEATURE_MODEL_PATTERN.match(filename)
        ],
        key=feature_model_index,
    )


def read_dimacs(dimacs_path: str) -> DimacsReader:
    reader = DimacsReader()
    reader.fromFile(dimacs_path)

    if not reader.features:
        raise ValueError(f"No feature comments found in {dimacs_path}")

    if reader.nFeatures != len(reader.features):
        raise ValueError(
            f"Feature count mismatch in {dimacs_path}: "
            f"header={reader.nFeatures}, comments={len(reader.features)}"
        )

    return reader


def get_feature_names(reader: DimacsReader) -> list[str]:
    return [reader.features[feature_id] for feature_id in sorted(reader.features)]


def build_feature_costs(feature_names: list[str]) -> list[dict[str, int | str]]:
    """Reproduce the source project's random feature costs for one model."""
    feature_costs = np.random.randint(
        MIN_FEATURE_COST,
        MAX_FEATURE_COST + 1,
        size=len(feature_names),
    )

    return [
        {"name": feature_name, "cost": int(feature_cost)}
        for feature_name, feature_cost in zip(feature_names, feature_costs)
    ]


def format_literal(literal: int, features: dict[int, str]) -> str:
    feature_name = features[abs(literal)]
    if literal < 0:
        return f"not {feature_name}"
    return feature_name


def format_clause(clause: list[int], features: dict[int, str]) -> str:
    literals = [literal for literal in clause if literal != 0]
    return " or ".join(format_literal(literal, features) for literal in literals)


def build_constraints(reader: DimacsReader) -> list[dict[str, int | str]]:
    return [
        {"id": constraint_id, "constraint": format_clause(clause, reader.features)}
        for constraint_id, clause in enumerate(reader.clauses, start=1)
    ]


def save_json(output_path: str, data: list[dict[str, int | str]]) -> str:
    os.makedirs(JSON_DIR, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=2)

    return output_path


def save_feature_costs(model_index: int, feature_costs: list[dict[str, int | str]]) -> str:
    output_path = os.path.join(JSON_DIR, f"feature_model_cost_{model_index}.json")
    return save_json(output_path, feature_costs)


def save_constraints(model_index: int, constraints: list[dict[str, int | str]]) -> str:
    output_path = os.path.join(JSON_DIR, f"feature_model_constraint_{model_index}.json")
    return save_json(output_path, constraints)


def main() -> None:
    np.random.seed(RANDOM_SEED)

    for dimacs_path in get_feature_model_paths():
        model_index = feature_model_index(dimacs_path)
        reader = read_dimacs(dimacs_path)
        feature_names = get_feature_names(reader)

        feature_costs = build_feature_costs(feature_names)
        constraints = build_constraints(reader)

        cost_path = save_feature_costs(model_index, feature_costs)
        constraint_path = save_constraints(model_index, constraints)
        print(f"Saved feature_model_{model_index} costs to {cost_path}")
        print(f"Saved feature_model_{model_index} constraints to {constraint_path}")


if __name__ == "__main__":
    main()
