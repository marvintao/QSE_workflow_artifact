# Use Cases

This directory contains the benchmark instances, problem definitions, and generated task-level requirements used by the QSE workflow. The generated task-level requirements ask an agentic system to formulate software-engineering optimization problems, solve them with quantum algorithms, and produce the corresponding application/report.

The current generated set contains 20 requirement files for test-case optimization benchmarks.

## Directory Layout

| Path | Purpose |
|:---|:---|
| [config.yaml](./config.yaml) | Lists the benchmark families and problem names used by the processing and generation scripts. |
| [req_template.jinja](./req_template.jinja) | Jinja template for rendering each natural-language requirement file. |
| [output_frame.md](./output_frame.md) | Optional report-format instructions inserted into generated task-level requirements. If empty, a default sentence is used. |
| [problem_def/](./problem_def) | Markdown definitions for the four supported optimization problems. |
| [benchmark/original/](./benchmark/original) | Raw benchmark artifacts copied from the source projects/papers. |
| [benchmark/json/](./benchmark/json) | Normalized JSON benchmark instances consumed by the requirement generator. |
| [benchmark/objectives.json](./benchmark/objectives.json) | Objective descriptions for non-configuration benchmarks. |
| [benchmark/process_IGDec-QAOA.py](./benchmark/process_IGDec-QAOA.py) | Converts IGDec-QAOA CSV benchmarks into normalized JSON objective files. |
| [benchmark/process_SelectQA.py](./benchmark/process_SelectQA.py) | Converts SelectQA/SIR raw coverage and fault data into normalized JSON objective files. |
| [benchmark/process_configuration.py](./benchmark/process_configuration.py) | Converts configuration DIMACS benchmarks into feature-cost and constraint JSON files. |
| [requirements/req_gen.py](./requirements/req_gen.py) | Generates requirement text files and the requirement overview JSON. |
| [requirements/req_para.json](./requirements/req_para.json) | Optional parameter guidance keyed by problem type and constrained-problem type. |
| [requirements/req_txt/](./requirements/req_txt) | Generated requirement files named `req_0.txt` through `req_19.txt`. |
| [requirements/req_overview.json](./requirements/req_overview.json) | Machine-readable mapping from requirement id to problem, benchmark, constraint file, and prioritization `m` value. |

## Supported Problems

| Problem | Definition |
|:---|:---|
| `test case selection` | [problem_def/test_case_selection.md](./problem_def/test_case_selection.md) |
| `test case minimization` | [problem_def/test_case_minimization.md](./problem_def/test_case_minimization.md) |
| `configuration selection` | [problem_def/configuration_selection.md](./problem_def/configuration_selection.md) |
| `configuration prioritization` | [problem_def/configuration_prioritization.md](./problem_def/configuration_prioritization.md) |

The problem-definition directory also includes [problem_def/README.md](./problem_def/README.md), which records reference literature for human readers. Generated task-level requirements should be self-contained; agents solving the requirements should not need to research the cited papers.

## Benchmark Data

### IGDec-QAOA Benchmarks

`benchmark/process_IGDec-QAOA.py` reads CSV files from `benchmark/original/` and writes JSON files to `benchmark/json/`.

| Output JSON | Objective fields |
|:---|:---|
| [gsdtsr.json](./benchmark/json/gsdtsr.json) | `id`, `time`, `rate` |
| [iofrol.json](./benchmark/json/iofrol.json) | `id`, `time`, `rate` |
| [paintcontrol.json](./benchmark/json/paintcontrol.json) | `id`, `time`, `rate` |
| [sampled_paintcontrol.json](./benchmark/json/sampled_paintcontrol.json) | `id`, `time`, `rate` |
| [elevator_o2.json](./benchmark/json/elevator_o2.json) | `id`, `cost`, `input_div` |
| [elevator_o3.json](./benchmark/json/elevator_o3.json) | `id`, `cost`, `pcount`, `dist` |

`elevator_o2` and `elevator_o3` are two derived views of `benchmark/original/elevator.csv` with different objective sets.

### SelectQA/SIR Benchmarks

`benchmark/process_SelectQA.py` reads SIR program data under `benchmark/original/{flex,grep,gzip,sed}/` and writes normalized objective JSON files.

| Output JSON | Objective fields |
|:---|:---|
| [flex.json](./benchmark/json/flex.json) | `id`, `statement_cov`, `execution_cost`, `faults_cov` |
| [grep.json](./benchmark/json/grep.json) | `id`, `statement_cov`, `execution_cost`, `faults_cov` |
| [gzip.json](./benchmark/json/gzip.json) | `id`, `statement_cov`, `execution_cost`, `faults_cov` |
| [sed.json](./benchmark/json/sed.json) | `id`, `statement_cov`, `execution_cost`, `faults_cov` |

The script reads `fault-matrix.txt` for historical fault detection and per-test `*.gcov.json` files for execution cost and statement coverage.

### Configuration Benchmarks

`benchmark/process_configuration.py` reads DIMACS files from `benchmark/original/config_opt/` and writes two JSON files per feature model.

| Output pattern | Meaning |
|:---|:---|
| `feature_model_cost_[N].json` | Feature dictionaries of the form `{ "name": "...", "cost": ... }`. |
| `feature_model_constraint_[N].json` | CNF constraints rendered as readable disjunctions, for example `A1 or not C2`. |

The current normalized data covers `feature_model_0` through `feature_model_19`. Feature costs are reproduced with:

```python
np.random.seed(42)
np.random.randint(10, 101, size=n)
```

The feature models are processed in numeric order so that reproduced random costs match the source evaluation setup.

## Objective Descriptions

[benchmark/objectives.json](./benchmark/objectives.json) provides descriptions for the objectives rendered into the `Optimization Target` section of each requirement.

| Benchmark group | Maximize | Minimize |
|:---|:---|:---|
| `paintcontrol`, `sampled_paintcontrol`, `iofrol`, `gsdtsr` | `rate` | `time` |
| `elevator_o2` | `input_div` | `cost` |
| `elevator_o3` | `pcount`, `dist` | `cost` |
| `flex`, `grep`, `gzip`, `sed` | `statement_cov`, `faults_cov` | `execution_cost` |
| `feature_model_0` through `feature_model_19` | none by default | `cost` |

Configuration benchmarks do not have explicit entries in `objectives.json`. `requirements/req_gen.py` supplies a default minimization objective for `cost`.

## Configuration

[config.yaml](./config.yaml) currently contains:

| Key | Current values | Used by |
|:---|:---|:---|
| `IGDecQAOA_bench` | `gsdtsr`, `iofrol`, `paintcontrol`, `sampled_paintcontrol` | `process_IGDec-QAOA.py`, `req_gen.py` |
| `SelectQA_bench` | `flex`, `grep`, `gsdtsr`, `gzip` | `process_SelectQA.py`, `req_gen.py` |
| `problem_name` | `test case minimization`, `test case selection` | Documentation/reference |

`req_gen.py` also has a built-in test-case benchmark list:

```text
elevator_o2, elevator_o3, gsdtsr, iofrol, paintcontrol,
sampled_paintcontrol, flex, grep, gzip, sed
```

The generated test-case requirements are based on the union of this built-in list, `IGDecQAOA_bench`, and `SelectQA_bench`, filtered by available files in `benchmark/json/`.

### [requirements/req_para.json](./requirements/req_para.json)

Defines optional parameter settings inserted into the `Parameter Settings` section of generated task-level requirements.

| Key | Meaning |
|:---|:---|
| `problem` | Parameter guidance keyed by optimization problem name. If the value is a list, `req_gen.py` generates one requirement per list item for that problem/benchmark pair. |
| `constraint` | Parameter guidance keyed by optimization problem name, used only when the benchmark has an explicit constraint file. |

The current generated requirement set does not use configuration-optimization parameter guidance.

## Generation Workflow

Run commands from this directory:

```powershell
python .\benchmark\process_IGDec-QAOA.py
python .\benchmark\process_SelectQA.py
python .\requirements\req_gen.py
```

The benchmark processing scripts regenerate normalized data under `benchmark/json/`. The requirement generator then writes:

- `requirements/req_txt/req_0.txt` through `requirements/req_txt/req_19.txt`.
- `requirements/req_overview.json`.

When `requirements/req_gen.py` runs, it deletes existing `req_*.txt` files in `requirements/req_txt/` before writing the new generated set.

Note: `process_SelectQA.py` only supports raw SIR program directories for `flex`, `grep`, `gzip`, and `sed`. If regenerating SelectQA data from raw files, make sure `SelectQA_bench` contains only supported SIR program names. The current `req_gen.py` run can still use all existing normalized JSON files in `benchmark/json/`.

## Requirement Template

[req_template.jinja](./req_template.jinja) renders each requirement with the following values:

| Variable | Source |
|:---|:---|
| `req_id` | Numeric requirement id, starting from `0`. |
| `problem_name` | Problem type, for example `test case selection`. |
| `problem_definition` | Matching markdown file from `problem_def/`. |
| `instance_name` | Benchmark name, for example `elevator_o2` or `feature_model_0`. |
| `instance` | Pretty-printed JSON benchmark data from `benchmark/json/`. |
| `constraints` | Constraint JSON for feature models; otherwise default text. |
| `opt_max` | Objectives to maximize from `objectives.json`; otherwise default text. |
| `opt_min` | Objectives to minimize from `objectives.json` or the configuration default. |
| `parameters` | Parameter guidance from `requirements/req_para.json`; otherwise default text. |
| `output_formats` | Content of `output_frame.md`; otherwise default text. |

If no parameter guidance applies, the default parameter text is:

```text
No specific parameter settings provided.
```

If [output_frame.md](./output_frame.md) is empty, the default output-format text is:

```text
No specific output formats required.
```

## Current Requirement Mapping

The authoritative machine-readable mapping is [requirements/req_overview.json](./requirements/req_overview.json). The current human-readable mapping is:

| Req ID | Problem | Benchmark Instance | Constraint | m_for_prioritization |
|:---:|:---|:---|:---|:---:|
| [0](./requirements/req_txt/req_0.txt) | test case selection | [elevator_o2](./benchmark/json/elevator_o2.json) | No | None |
| [1](./requirements/req_txt/req_1.txt) | test case selection | [elevator_o3](./benchmark/json/elevator_o3.json) | No | None |
| [2](./requirements/req_txt/req_2.txt) | test case selection | [gsdtsr](./benchmark/json/gsdtsr.json) | No | None |
| [3](./requirements/req_txt/req_3.txt) | test case selection | [iofrol](./benchmark/json/iofrol.json) | No | None |
| [4](./requirements/req_txt/req_4.txt) | test case selection | [paintcontrol](./benchmark/json/paintcontrol.json) | No | None |
| [5](./requirements/req_txt/req_5.txt) | test case selection | [sampled_paintcontrol](./benchmark/json/sampled_paintcontrol.json) | No | None |
| [6](./requirements/req_txt/req_6.txt) | test case selection | [flex](./benchmark/json/flex.json) | No | None |
| [7](./requirements/req_txt/req_7.txt) | test case selection | [grep](./benchmark/json/grep.json) | No | None |
| [8](./requirements/req_txt/req_8.txt) | test case selection | [gzip](./benchmark/json/gzip.json) | No | None |
| [9](./requirements/req_txt/req_9.txt) | test case selection | [sed](./benchmark/json/sed.json) | No | None |
| [10](./requirements/req_txt/req_10.txt) | test case minimization | [elevator_o2](./benchmark/json/elevator_o2.json) | No | None |
| [11](./requirements/req_txt/req_11.txt) | test case minimization | [elevator_o3](./benchmark/json/elevator_o3.json) | No | None |
| [12](./requirements/req_txt/req_12.txt) | test case minimization | [gsdtsr](./benchmark/json/gsdtsr.json) | No | None |
| [13](./requirements/req_txt/req_13.txt) | test case minimization | [iofrol](./benchmark/json/iofrol.json) | No | None |
| [14](./requirements/req_txt/req_14.txt) | test case minimization | [paintcontrol](./benchmark/json/paintcontrol.json) | No | None |
| [15](./requirements/req_txt/req_15.txt) | test case minimization | [sampled_paintcontrol](./benchmark/json/sampled_paintcontrol.json) | No | None |
| [16](./requirements/req_txt/req_16.txt) | test case minimization | [flex](./benchmark/json/flex.json) | No | None |
| [17](./requirements/req_txt/req_17.txt) | test case minimization | [grep](./benchmark/json/grep.json) | No | None |
| [18](./requirements/req_txt/req_18.txt) | test case minimization | [gzip](./benchmark/json/gzip.json) | No | None |
| [19](./requirements/req_txt/req_19.txt) | test case minimization | [sed](./benchmark/json/sed.json) | No | None |

## Benchmark Sources

The included benchmarks come from open-source artifacts of existing literature.

| Ref | Benchmarks | Property | Source |
|:---:|:---|:---:|:---|
| [1](#ref-1) | `elevator_o2`, `elevator_o3`, `gsdtsr`, `iofrol`, `paintcontrol`, `sampled_paintcontrol` | Real world | IGDec-QAOA benchmark artifacts. |
| [2](#ref-2) | `flex`, `grep`, `gzip`, `sed` | Real world | SelectQA/SIR benchmark artifacts. |
| [3](#ref-3) | `feature_model_0` through `feature_model_19` | Artificial | Configuration optimization DIMACS feature-model artifacts. |

<a id="ref-1"></a>[1] Wang X, Ali S, Yue T, et al. Quantum approximate optimization algorithm for test case optimization[J]. IEEE Transactions on Software Engineering, 2024, 50(12): 3249-3264. Artifact: https://zenodo.org/records/13911651

<a id="ref-2"></a>[2] Trovato A, De Stefano M, Pecorelli F, et al. Reformulating regression test suite optimization using quantum annealing-an empirical study[J]. International Journal on Software Tools and Technology Transfer, 2024, 26(6): 767-780. Artifact: https://github.com/AntonioTrovato/SelectQA/tree/main/SIR_Programs

<a id="ref-3"></a>[3] Ammermann J, Brenneisen F J, Bittner T, et al. Quantum Solution for Configuration Selection and Prioritization[C]//Proceedings of the 5th ACM/IEEE International Workshop on Quantum Software Engineering. 2024: 21-28. Artifact: https://github.com/KIT-TVA/qc-configuration-problem/tree/develop/benchmarks
