# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

import json
import os
import re
from typing import Any

import yaml
from jinja2 import Environment


DIRECTORY = os.path.dirname(os.path.abspath(__file__))
USE_CASES_DIR = os.path.dirname(DIRECTORY)
BENCHMARK_DIR = os.path.join(USE_CASES_DIR, "benchmark")
BENCHMARK_JSON_DIR = os.path.join(BENCHMARK_DIR, "json")
PROBLEM_DEF_DIR = os.path.join(USE_CASES_DIR, "problem_def")
REQ_TXT_DIR = os.path.join(DIRECTORY, "req_txt")
REQ_OVERVIEW_PATH = os.path.join(DIRECTORY, "req_overview.json")
REQ_PARA_PATH = os.path.join(DIRECTORY, "req_para.json")

CONFIG_PATH = os.path.join(USE_CASES_DIR, "config.yaml")
README_PATH = os.path.join(USE_CASES_DIR, "README.md")
OBJECTIVES_PATH = os.path.join(BENCHMARK_DIR, "objectives.json")
OUTPUT_FRAME_PATH = os.path.join(USE_CASES_DIR, "output_frame.md")
TEMPLATE_PATH = os.path.join(USE_CASES_DIR, "req_template.jinja")

DEFAULT_PROBLEM_DEFINITION = "No specific problem definition provided."
DEFAULT_INSTANCE = "No specific benchmark instance provided."
DEFAULT_CONSTRAINTS = "No specific constraints provided."
DEFAULT_OPT_MAX = "No specific objectives to maximize."
DEFAULT_OPT_MIN = "No specific objectives to minimize."
DEFAULT_OUTPUT_FORMATS = "No specific output formats required."
DEFAULT_PARAMETERS = "No specific parameter settings provided."
DEFAULT_OPT_OBJ = "do not specify any objectives"

FEATURE_MODEL_RE = re.compile(r"^feature_model_cost_(\d+)\.json$")
README_BENCHMARK_RE = re.compile(r"\|\s*\d+\s*\|\s*\[([^\]]+)\]\(([^)]+)\)")

TEST_CASE_BENCHMARKS = [
    "elevator_o2",
    "elevator_o3",
    "gsdtsr",
    "iofrol",
    "paintcontrol",
    "sampled_paintcontrol",
    "flex",
    "grep",
    "gzip",
    "sed",
]


def read_text_or_default(path: str, default: str) -> str:
    if not os.path.exists(path):
        return default

    with open(path, "r", encoding="utf-8") as input_file:
        content = input_file.read().strip()
    return content if content else default


def read_json_text_or_default(path: str, default: str) -> str:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return default

    with open(path, "r", encoding="utf-8") as input_file:
        data = json.load(input_file)
    return json.dumps(data, ensure_ascii=False, indent=2)


def load_config() -> dict[str, list[str]]:
    content = read_text_or_default(CONFIG_PATH, "")
    if not content:
        return {}

    loaded = yaml.safe_load(content)
    return loaded or {}


def load_objectives() -> dict[str, Any]:
    if not os.path.exists(OBJECTIVES_PATH) or os.path.getsize(OBJECTIVES_PATH) == 0:
        return {}

    with open(OBJECTIVES_PATH, "r", encoding="utf-8") as objectives_file:
        return json.load(objectives_file)


def load_req_parameters() -> dict[str, Any]:
    """Load optional parameter guidance used when rendering requirements.

    `req_para.json` currently has two namespaces:

    - `problem`: parameter guidance keyed by optimization problem name.
    - `constraint`: parameter guidance keyed by optimization problem name, used
      only when the selected benchmark instance has an explicit constraint file.

    Missing or empty files are treated as no additional parameter guidance.
    """
    if not os.path.exists(REQ_PARA_PATH) or os.path.getsize(REQ_PARA_PATH) == 0:
        return {}

    with open(REQ_PARA_PATH, "r", encoding="utf-8") as req_para_file:
        loaded = json.load(req_para_file)

    return loaded if isinstance(loaded, dict) else {}


def parse_readme_benchmarks() -> dict[str, dict[str, str | None]]:
    content = read_text_or_default(README_PATH, "")
    benchmarks: dict[str, dict[str, str | None]] = {}

    for match in README_BENCHMARK_RE.finditer(content):
        name = match.group(1).strip()
        link = match.group(2).strip()
        if not link.startswith("./json/"):
            continue

        instance_file = os.path.basename(link)
        benchmarks[name] = {
            "instance_file": instance_file,
            "constraint_file": None,
        }

    return benchmarks


def discover_feature_model_benchmarks() -> dict[str, dict[str, str | None]]:
    benchmarks: dict[str, dict[str, str | None]] = {}

    for filename in os.listdir(BENCHMARK_JSON_DIR):
        match = FEATURE_MODEL_RE.match(filename)
        if match is None:
            continue

        model_id = match.group(1)
        name = f"feature_model_{model_id}"
        constraint_name = f"feature_model_constraint_{model_id}.json"
        constraint_path = os.path.join(BENCHMARK_JSON_DIR, constraint_name)
        benchmarks[name] = {
            "instance_file": filename,
            "constraint_file": constraint_name if os.path.exists(constraint_path) else None,
        }

    return dict(sorted(benchmarks.items(), key=lambda item: int(item[0].split("_")[-1])))


def discover_benchmarks() -> dict[str, dict[str, str | None]]:
    benchmarks = parse_readme_benchmarks()
    benchmarks.update(discover_feature_model_benchmarks())

    for filename in os.listdir(BENCHMARK_JSON_DIR):
        if not filename.endswith(".json"):
            continue

        name = os.path.splitext(filename)[0]
        if name.startswith("feature_model_cost_") or name.startswith("feature_model_constraint_"):
            continue
        if re.match(r"feature_model_\d+$", name):
            continue
        benchmarks.setdefault(name, {"instance_file": filename, "constraint_file": None})
        benchmarks[name]["instance_file"] = filename

    return dict(sorted(benchmarks.items()))


def get_problem_display_name(problem_name: str) -> str:
    """Convert internal file-style problem names to rendered requirement names."""
    return problem_name.replace("_", " ")


def get_parameter_candidates(problem_name: str, req_parameters: dict[str, Any]) -> list[str | None]:
    """Return generation candidates for a problem-level parameter.

    Most problems produce one requirement per benchmark and therefore return a
    single `None` candidate. If `req_para.json` provides a list for the problem,
    each list item becomes one generated requirement for the same benchmark.
    This is used by configuration prioritization to generate one requirement per
    candidate `m` value.
    """
    problem_display_name = get_problem_display_name(problem_name)
    problem_parameters = req_parameters.get("problem", {})
    if not isinstance(problem_parameters, dict):
        return [None]

    value = problem_parameters.get(problem_display_name)
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return [None]


def build_problem_benchmark_pairs(
    config: dict[str, list[str]],
    benchmarks: dict[str, dict[str, str | None]],
    req_parameters: dict[str, Any],
) -> list[tuple[str, str, str | None]]:
    """Build the ordered requirement generation plan.

    The first two tuple fields are the problem name and benchmark name. The
    third field is a selected problem-level parameter candidate, if this
    requirement is generated from a parameter list in `req_para.json`.
    """
    test_case_benchmarks = dict.fromkeys(
        TEST_CASE_BENCHMARKS
        + config.get("IGDecQAOA_bench", [])
        + config.get("SelectQA_bench", [])
    )

    pairs: list[tuple[str, str, str | None]] = []

    for problem_name in ("test_case_selection", "test_case_minimization"):
        for benchmark in test_case_benchmarks:
            if benchmark in benchmarks:
                pairs.append((problem_name, benchmark, None))

    return pairs


def get_problem_definition(problem_name: str) -> str:
    problem_definition_path = os.path.join(PROBLEM_DEF_DIR, f"{problem_name}.md")
    return read_text_or_default(problem_definition_path, DEFAULT_PROBLEM_DEFINITION)


def get_objective_spec(benchmark_name: str, objectives: dict[str, Any]) -> dict[str, dict[str, str]]:
    spec = objectives.get(benchmark_name, {})

    if benchmark_name.startswith("feature_model_") and not spec:
        return {
            "maximize": {},
            "minimize": {
                "cost": "The total feature cost of a selected valid configuration."
            },
        }

    return {
        "maximize": spec.get("maximize", {}) if isinstance(spec, dict) else {},
        "minimize": spec.get("minimize", {}) if isinstance(spec, dict) else {},
    }


def format_objectives(objectives: dict[str, str], default: str) -> str:
    if not objectives:
        return default

    return "\n  ".join(f"* {key}: {value}" for key, value in objectives.items())


def format_parameters(parameter_lines: list[str]) -> str:
    """Render parameter guidance as markdown bullets for the template."""
    if not parameter_lines:
        return DEFAULT_PARAMETERS

    return "\n  ".join(f"* {line}" for line in parameter_lines)


def get_constraint_parameter(
    problem_name: str,
    has_constraints: bool,
    req_parameters: dict[str, Any],
) -> str | None:
    """Return constraint-specific parameter guidance when a benchmark is constrained."""
    if not has_constraints:
        return None

    constraint_parameters = req_parameters.get("constraint", {})
    if not isinstance(constraint_parameters, dict):
        return None

    value = constraint_parameters.get(get_problem_display_name(problem_name))
    return str(value) if isinstance(value, str) else None


def build_parameter_lines(
    problem_name: str,
    benchmark_info: dict[str, str | None],
    selected_problem_parameter: str | None,
    req_parameters: dict[str, Any],
) -> list[str]:
    """Collect all parameter guidance that applies to a generated requirement."""
    parameter_lines: list[str] = []

    if selected_problem_parameter:
        parameter_lines.append(selected_problem_parameter)

    constraint_parameter = get_constraint_parameter(
        problem_name,
        has_constraints=bool(benchmark_info.get("constraint_file")),
        req_parameters=req_parameters,
    )
    if constraint_parameter:
        parameter_lines.append(constraint_parameter)

    return parameter_lines


def extract_m_for_prioritization(problem_name: str, selected_problem_parameter: str | None) -> int | None:
    """Extract the `m` value from a configuration-prioritization parameter line."""
    if problem_name != "configuration_prioritization" or not selected_problem_parameter:
        return None

    match = re.search(r"parameter\s+\$?m\$?.*?\bbe\s+(\d+)\b", selected_problem_parameter)
    return int(match.group(1)) if match else None


def format_objective_keys(maximize: dict[str, str], minimize: dict[str, str]) -> str:
    keys = list(maximize.keys()) + [key for key in minimize.keys() if key not in maximize]
    if not keys:
        return DEFAULT_OPT_OBJ
    return ", ".join(keys)


def render_requirement(template: str, context: dict[str, Any]) -> str:
    env = Environment(autoescape=False, keep_trailing_newline=True)
    return env.from_string(template).render(**context)


def build_context(
    req_id: int,
    problem_name: str,
    benchmark_name: str,
    benchmark_info: dict[str, str | None],
    objectives: dict[str, Any],
    selected_problem_parameter: str | None,
    req_parameters: dict[str, Any],
) -> dict[str, Any]:
    instance_file = benchmark_info.get("instance_file")
    constraint_file = benchmark_info.get("constraint_file")

    objective_spec = get_objective_spec(benchmark_name, objectives)
    maximize = objective_spec["maximize"]
    minimize = objective_spec["minimize"]

    instance = DEFAULT_INSTANCE
    if instance_file:
        instance_path = os.path.join(BENCHMARK_JSON_DIR, instance_file)
        instance = read_json_text_or_default(instance_path, DEFAULT_INSTANCE)

    constraints = DEFAULT_CONSTRAINTS
    if constraint_file:
        constraint_path = os.path.join(BENCHMARK_JSON_DIR, constraint_file)
        constraints = read_json_text_or_default(constraint_path, DEFAULT_CONSTRAINTS)

    parameter_lines = build_parameter_lines(
        problem_name,
        benchmark_info,
        selected_problem_parameter,
        req_parameters,
    )

    return {
        "req_id": req_id,
        "problem_name": get_problem_display_name(problem_name),
        "instance_name": benchmark_name,
        "problem_definition": get_problem_definition(problem_name),
        "instance": instance,
        "constraints": constraints,
        "opt_obj": format_objective_keys(maximize, minimize),
        "opt_max": format_objectives(maximize, DEFAULT_OPT_MAX),
        "opt_min": format_objectives(minimize, DEFAULT_OPT_MIN),
        "parameters": format_parameters(parameter_lines),
        "output_formats": read_text_or_default(OUTPUT_FRAME_PATH, DEFAULT_OUTPUT_FORMATS),
    }


def generate_requirements() -> list[str]:
    template = read_text_or_default(TEMPLATE_PATH, "")
    if not template:
        raise ValueError(f"Template is empty or missing: {TEMPLATE_PATH}")

    config = load_config()
    objectives = load_objectives()
    req_parameters = load_req_parameters()
    benchmarks = discover_benchmarks()
    pairs = build_problem_benchmark_pairs(config, benchmarks, req_parameters)

    os.makedirs(REQ_TXT_DIR, exist_ok=True)
    for filename in os.listdir(REQ_TXT_DIR):
        if re.match(r"^req_.*\.txt$", filename):
            os.remove(os.path.join(REQ_TXT_DIR, filename))

    output_paths: list[str] = []
    req_overview: dict[int, dict[str, Any]] = {}
    for req_id, (problem_name, benchmark_name, selected_problem_parameter) in enumerate(pairs):
        benchmark_info = benchmarks[benchmark_name]
        context = build_context(
            req_id,
            problem_name,
            benchmark_name,
            benchmark_info,
            objectives,
            selected_problem_parameter,
            req_parameters,
        )
        output_path = os.path.join(REQ_TXT_DIR, f"req_{req_id}.txt")
        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write(render_requirement(template, context))
        output_paths.append(output_path)
        req_overview[req_id] = {
            "problem": get_problem_display_name(problem_name),
            "benchmark": benchmark_name,
            "constraint": benchmark_info.get("constraint_file") or "No",
            "m_for_prioritization": extract_m_for_prioritization(problem_name, selected_problem_parameter),
        }

    with open(REQ_OVERVIEW_PATH, "w", encoding="utf-8") as overview_file:
        overview_file.write(json.dumps(req_overview, ensure_ascii=False, indent=2) + "\n")

    return output_paths


def main() -> None:
    output_paths = generate_requirements()
    print(f"Generated {len(output_paths)} requirement files in {REQ_TXT_DIR}")
    for output_path in output_paths:
        print(output_path)


if __name__ == "__main__":
    main()
