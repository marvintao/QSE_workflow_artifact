"""Sample large user-requirement instances for QSE workflow experiments.

The script samples test-case optimization and configuration optimization
requirements separately. Within each group, requirements are sorted by instance
size in descending order, where size is:

    number of tests/configurations + number of constraints

The output JSON records each sampled requirement file and its computed size.
"""

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Any


USE_CASES_DIR = os.path.dirname(os.path.abspath(__file__))
REQ_TXT_DIR = os.path.join(USE_CASES_DIR, "requirements", "req_txt")
REQ_OVERVIEW_PATH = os.path.join(USE_CASES_DIR, "requirements", "req_overview.json")
BENCHMARK_JSON_DIR = os.path.join(USE_CASES_DIR, "benchmark", "json")
OUTPUT_PATH = os.path.join(USE_CASES_DIR, "sampled_id.json")

TEST_CASE_PROBLEMS = {
    "test case selection",
    "test case minimization",
}
CONFIGURATION_PROBLEMS = {
    "configuration selection",
    "configuration prioritization",
}

REQ_FILE_RE = re.compile(r"^req_(\d+)\.txt$")
FEATURE_MODEL_RE = re.compile(r"^feature_model_(\d+)$")


@dataclass(frozen=True)
class Candidate:
    req_id: int
    filename: str
    problem: str
    benchmark: str
    instance_count: int
    constraint_count: int

    @property
    def score(self) -> int:
        return self.instance_count + self.constraint_count


SampledGroup = dict[str, list[dict[str, int | str]]]


def load_json(path: str) -> Any:
    """Load a UTF-8 JSON file."""
    with open(path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


def count_json_items(path: str) -> int:
    """Count top-level benchmark items in a normalized JSON file."""
    data = load_json(path)
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return len(data)
    raise ValueError(f"Unsupported JSON top-level type in {path}: {type(data).__name__}")


def parse_req_id(filename: str) -> int | None:
    """Extract the numeric requirement id from a filename such as req_12.txt."""
    match = REQ_FILE_RE.match(filename)
    return int(match.group(1)) if match else None


def sorted_requirement_files(req_txt_dir: str) -> list[str]:
    """Return req_*.txt filenames sorted by numeric requirement id."""
    return sorted(
        (filename for filename in os.listdir(req_txt_dir) if parse_req_id(filename) is not None),
        key=parse_req_id, # type: ignore
    ) # type: ignore


def benchmark_files(benchmark_name: str) -> tuple[str, str | None]:
    """Return benchmark data and optional constraint filenames for an instance."""
    feature_match = FEATURE_MODEL_RE.match(benchmark_name)
    if feature_match:
        model_id = feature_match.group(1)
        return (
            f"feature_model_cost_{model_id}.json",
            f"feature_model_constraint_{model_id}.json",
        )
    return f"{benchmark_name}.json", None


def build_candidate(req_filename: str, overview: dict[str, Any]) -> Candidate:
    """Build a sortable sampling candidate from requirement metadata."""
    req_id = parse_req_id(req_filename)
    if req_id is None:
        raise ValueError(f"Requirement file does not match req_*.txt: {req_filename}")

    metadata = overview.get(str(req_id))
    if not isinstance(metadata, dict):
        raise KeyError(f"Missing requirement {req_id} in {REQ_OVERVIEW_PATH}")

    problem = metadata["problem"]
    benchmark = metadata["benchmark"]
    instance_file, default_constraint_file = benchmark_files(benchmark)
    instance_path = os.path.join(BENCHMARK_JSON_DIR, instance_file)
    if not os.path.exists(instance_path):
        raise FileNotFoundError(f"Missing benchmark JSON for {req_filename}: {instance_path}")

    constraint_file = metadata.get("constraint")
    if not constraint_file or constraint_file == "No":
        constraint_file = default_constraint_file if problem in CONFIGURATION_PROBLEMS else None

    constraint_count = 0
    if constraint_file:
        constraint_path = os.path.join(BENCHMARK_JSON_DIR, constraint_file)
        if os.path.exists(constraint_path):
            constraint_count = count_json_items(constraint_path)

    return Candidate(
        req_id=req_id,
        filename=req_filename,
        problem=problem,
        benchmark=benchmark,
        instance_count=count_json_items(instance_path),
        constraint_count=constraint_count,
    )


def sample_top(candidates: list[Candidate], problems: set[str], sample_size: int) -> list[Candidate]:
    """Sample the largest candidates for a problem family."""
    problem_candidates = [candidate for candidate in candidates if candidate.problem in problems]

    # Sorting criterion:
    # 1. descending size = tests/configurations count + constraints count
    # 2. descending instance count
    # 3. descending constraint count
    # 4. ascending req id for deterministic tie breaking
    sorted_candidates = sorted(
        problem_candidates,
        key=lambda candidate: (
            -candidate.score,
            -candidate.instance_count,
            -candidate.constraint_count,
            candidate.req_id,
        ),
    )
    return sorted_candidates[:sample_size]


def sample_requirements(
    sample_size: int = 10,
    req_txt_dir: str = REQ_TXT_DIR,
    overview_path: str = REQ_OVERVIEW_PATH,
) -> SampledGroup:
    """Sample test-case and configuration optimization requirements separately."""
    overview = load_json(overview_path)
    if not isinstance(overview, dict):
        raise ValueError(f"Requirement overview must be a JSON object: {overview_path}")

    candidates = [build_candidate(req_filename, overview) for req_filename in sorted_requirement_files(req_txt_dir)]
    sampled_test_cases = sample_top(candidates, TEST_CASE_PROBLEMS, sample_size)
    sampled_configurations = sample_top(candidates, CONFIGURATION_PROBLEMS, sample_size)
    return {
        "test case optimization": [candidate_metadata(candidate) for candidate in sampled_test_cases],
        "configuration optimization": [candidate_metadata(candidate) for candidate in sampled_configurations],
    }


def candidate_metadata(candidate: Candidate) -> dict[str, int | str]:
    """Convert a candidate to the required output metadata format."""
    return {
        "case_id": candidate.filename,
        "size": candidate.score,
    }


def write_sampled_ids(sampled_ids: SampledGroup, output_path: str = OUTPUT_PATH) -> None:
    """Write sampled metadata to JSON."""
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(sampled_ids, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sample top user-requirement files from req_txt by descending "
            "tests/configurations count plus constraints count."
        )
    )
    parser.add_argument(
        "-n",
        "--sample-size",
        type=int,
        default=10,
        help="number of test-case and configuration requirements to sample separately",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=OUTPUT_PATH,
        help="output JSON file containing sampled requirement metadata",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sample_size < 1:
        raise ValueError("--sample-size must be a positive integer")

    sampled_ids = sample_requirements(sample_size=args.sample_size)
    write_sampled_ids(sampled_ids, args.output)
    total_count = sum(len(group) for group in sampled_ids.values())
    print(f"Wrote {total_count} sampled requirement metadata entries to {args.output}")


if __name__ == "__main__":
    main()
