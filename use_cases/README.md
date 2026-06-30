# Use Cases

This directory contains the benchmark instances, problem definitions, and generated user requirements used by the QSE workflow. The generated requirements ask an agentic system to formulate software-engineering optimization problems, solve them with quantum algorithms, and produce the corresponding application/report.

The current generated set contains 80 requirement files:

- 20 requirements for test-case optimization benchmarks.
- 20 requirements for configuration selection feature models.
- 40 requirements for configuration prioritization feature models, generated from two `m` candidates in `requirements/req_para.json`.

## Directory Layout

| Path | Purpose |
|:---|:---|
| [config.yaml](./config.yaml) | Lists the benchmark families and problem names used by the processing and generation scripts. |
| [req_template.jinja](./req_template.jinja) | Jinja template for rendering each natural-language requirement file. |
| [output_frame.md](./output_frame.md) | Optional report-format instructions inserted into generated requirements. If empty, a default sentence is used. |
| [problem_def/](./problem_def) | Markdown definitions for the four supported optimization problems. |
| [benchmark/original/](./benchmark/original) | Raw benchmark artifacts copied from the source projects/papers. |
| [benchmark/json/](./benchmark/json) | Normalized JSON benchmark instances consumed by the requirement generator. |
| [benchmark/objectives.json](./benchmark/objectives.json) | Objective descriptions for non-configuration benchmarks. |
| [benchmark/process_IGDec-QAOA.py](./benchmark/process_IGDec-QAOA.py) | Converts IGDec-QAOA CSV benchmarks into normalized JSON objective files. |
| [benchmark/process_SelectQA.py](./benchmark/process_SelectQA.py) | Converts SelectQA/SIR raw coverage and fault data into normalized JSON objective files. |
| [benchmark/process_configuration.py](./benchmark/process_configuration.py) | Converts configuration DIMACS benchmarks into feature-cost and constraint JSON files. |
| [requirements/req_gen.py](./requirements/req_gen.py) | Generates requirement text files and the requirement overview JSON. |
| [requirements/req_para.json](./requirements/req_para.json) | Optional parameter guidance keyed by problem type and constrained-problem type. |
| [requirements/req_txt/](./requirements/req_txt) | Generated requirement files named `req_0.txt` through `req_79.txt`. |
| [requirements/req_overview.json](./requirements/req_overview.json) | Machine-readable mapping from requirement id to problem, benchmark, constraint file, and prioritization `m` value. |

## Supported Problems

| Problem | Definition |
|:---|:---|
| `test case selection` | [problem_def/test_case_selection.md](./problem_def/test_case_selection.md) |
| `test case minimization` | [problem_def/test_case_minimization.md](./problem_def/test_case_minimization.md) |
| `configuration selection` | [problem_def/configuration_selection.md](./problem_def/configuration_selection.md) |
| `configuration prioritization` | [problem_def/configuration_prioritization.md](./problem_def/configuration_prioritization.md) |

The problem-definition directory also includes [problem_def/README.md](./problem_def/README.md), which records reference literature for human readers. Generated requirements should be self-contained; agents solving the requirements should not need to research the cited papers.

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
| `problem_name` | `test case minimization`, `test case selection`, `configuration selection`, `configuration prioritization` | Documentation/reference |

`req_gen.py` also has a built-in test-case benchmark list:

```text
elevator_o2, elevator_o3, gsdtsr, iofrol, paintcontrol,
sampled_paintcontrol, flex, grep, gzip, sed
```

The generated test-case requirements are based on the union of this built-in list, `IGDecQAOA_bench`, and `SelectQA_bench`, filtered by available files in `benchmark/json/`.

### [requirements/req_para.json](./requirements/req_para.json)

Defines optional parameter settings inserted into the `Parameter Settings` section of generated requirements.

| Key | Meaning |
|:---|:---|
| `problem` | Parameter guidance keyed by optimization problem name. If the value is a list, `req_gen.py` generates one requirement per list item for that problem/benchmark pair. |
| `constraint` | Parameter guidance keyed by optimization problem name, used only when the benchmark has an explicit constraint file. |

The current `problem.configuration prioritization` value contains two `m` settings, so each feature model generates two configuration-prioritization requirements: one with `m = 1` and one with `m = 5`. The current `constraint.configuration selection` and `constraint.configuration prioritization` values add penalty-parameter guidance for constrained feature-model requirements.

## Generation Workflow

Run commands from this directory:

```powershell
python .\benchmark\process_IGDec-QAOA.py
python .\benchmark\process_SelectQA.py
python .\benchmark\process_configuration.py
python .\requirements\req_gen.py
```

The benchmark processing scripts regenerate normalized data under `benchmark/json/`. The requirement generator then writes:

- `requirements/req_txt/req_0.txt` through `requirements/req_txt/req_79.txt`.
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
| [20](./requirements/req_txt/req_20.txt) | configuration selection | [feature_model_0](./benchmark/json/feature_model_cost_0.json) | [feature_model_constraint_0.json](./benchmark/json/feature_model_constraint_0.json) | None |
| [21](./requirements/req_txt/req_21.txt) | configuration prioritization | [feature_model_0](./benchmark/json/feature_model_cost_0.json) | [feature_model_constraint_0.json](./benchmark/json/feature_model_constraint_0.json) | 1 |
| [22](./requirements/req_txt/req_22.txt) | configuration prioritization | [feature_model_0](./benchmark/json/feature_model_cost_0.json) | [feature_model_constraint_0.json](./benchmark/json/feature_model_constraint_0.json) | 5 |
| [23](./requirements/req_txt/req_23.txt) | configuration selection | [feature_model_1](./benchmark/json/feature_model_cost_1.json) | [feature_model_constraint_1.json](./benchmark/json/feature_model_constraint_1.json) | None |
| [24](./requirements/req_txt/req_24.txt) | configuration prioritization | [feature_model_1](./benchmark/json/feature_model_cost_1.json) | [feature_model_constraint_1.json](./benchmark/json/feature_model_constraint_1.json) | 1 |
| [25](./requirements/req_txt/req_25.txt) | configuration prioritization | [feature_model_1](./benchmark/json/feature_model_cost_1.json) | [feature_model_constraint_1.json](./benchmark/json/feature_model_constraint_1.json) | 5 |
| [26](./requirements/req_txt/req_26.txt) | configuration selection | [feature_model_2](./benchmark/json/feature_model_cost_2.json) | [feature_model_constraint_2.json](./benchmark/json/feature_model_constraint_2.json) | None |
| [27](./requirements/req_txt/req_27.txt) | configuration prioritization | [feature_model_2](./benchmark/json/feature_model_cost_2.json) | [feature_model_constraint_2.json](./benchmark/json/feature_model_constraint_2.json) | 1 |
| [28](./requirements/req_txt/req_28.txt) | configuration prioritization | [feature_model_2](./benchmark/json/feature_model_cost_2.json) | [feature_model_constraint_2.json](./benchmark/json/feature_model_constraint_2.json) | 5 |
| [29](./requirements/req_txt/req_29.txt) | configuration selection | [feature_model_3](./benchmark/json/feature_model_cost_3.json) | [feature_model_constraint_3.json](./benchmark/json/feature_model_constraint_3.json) | None |
| [30](./requirements/req_txt/req_30.txt) | configuration prioritization | [feature_model_3](./benchmark/json/feature_model_cost_3.json) | [feature_model_constraint_3.json](./benchmark/json/feature_model_constraint_3.json) | 1 |
| [31](./requirements/req_txt/req_31.txt) | configuration prioritization | [feature_model_3](./benchmark/json/feature_model_cost_3.json) | [feature_model_constraint_3.json](./benchmark/json/feature_model_constraint_3.json) | 5 |
| [32](./requirements/req_txt/req_32.txt) | configuration selection | [feature_model_4](./benchmark/json/feature_model_cost_4.json) | [feature_model_constraint_4.json](./benchmark/json/feature_model_constraint_4.json) | None |
| [33](./requirements/req_txt/req_33.txt) | configuration prioritization | [feature_model_4](./benchmark/json/feature_model_cost_4.json) | [feature_model_constraint_4.json](./benchmark/json/feature_model_constraint_4.json) | 1 |
| [34](./requirements/req_txt/req_34.txt) | configuration prioritization | [feature_model_4](./benchmark/json/feature_model_cost_4.json) | [feature_model_constraint_4.json](./benchmark/json/feature_model_constraint_4.json) | 5 |
| [35](./requirements/req_txt/req_35.txt) | configuration selection | [feature_model_5](./benchmark/json/feature_model_cost_5.json) | [feature_model_constraint_5.json](./benchmark/json/feature_model_constraint_5.json) | None |
| [36](./requirements/req_txt/req_36.txt) | configuration prioritization | [feature_model_5](./benchmark/json/feature_model_cost_5.json) | [feature_model_constraint_5.json](./benchmark/json/feature_model_constraint_5.json) | 1 |
| [37](./requirements/req_txt/req_37.txt) | configuration prioritization | [feature_model_5](./benchmark/json/feature_model_cost_5.json) | [feature_model_constraint_5.json](./benchmark/json/feature_model_constraint_5.json) | 5 |
| [38](./requirements/req_txt/req_38.txt) | configuration selection | [feature_model_6](./benchmark/json/feature_model_cost_6.json) | [feature_model_constraint_6.json](./benchmark/json/feature_model_constraint_6.json) | None |
| [39](./requirements/req_txt/req_39.txt) | configuration prioritization | [feature_model_6](./benchmark/json/feature_model_cost_6.json) | [feature_model_constraint_6.json](./benchmark/json/feature_model_constraint_6.json) | 1 |
| [40](./requirements/req_txt/req_40.txt) | configuration prioritization | [feature_model_6](./benchmark/json/feature_model_cost_6.json) | [feature_model_constraint_6.json](./benchmark/json/feature_model_constraint_6.json) | 5 |
| [41](./requirements/req_txt/req_41.txt) | configuration selection | [feature_model_7](./benchmark/json/feature_model_cost_7.json) | [feature_model_constraint_7.json](./benchmark/json/feature_model_constraint_7.json) | None |
| [42](./requirements/req_txt/req_42.txt) | configuration prioritization | [feature_model_7](./benchmark/json/feature_model_cost_7.json) | [feature_model_constraint_7.json](./benchmark/json/feature_model_constraint_7.json) | 1 |
| [43](./requirements/req_txt/req_43.txt) | configuration prioritization | [feature_model_7](./benchmark/json/feature_model_cost_7.json) | [feature_model_constraint_7.json](./benchmark/json/feature_model_constraint_7.json) | 5 |
| [44](./requirements/req_txt/req_44.txt) | configuration selection | [feature_model_8](./benchmark/json/feature_model_cost_8.json) | [feature_model_constraint_8.json](./benchmark/json/feature_model_constraint_8.json) | None |
| [45](./requirements/req_txt/req_45.txt) | configuration prioritization | [feature_model_8](./benchmark/json/feature_model_cost_8.json) | [feature_model_constraint_8.json](./benchmark/json/feature_model_constraint_8.json) | 1 |
| [46](./requirements/req_txt/req_46.txt) | configuration prioritization | [feature_model_8](./benchmark/json/feature_model_cost_8.json) | [feature_model_constraint_8.json](./benchmark/json/feature_model_constraint_8.json) | 5 |
| [47](./requirements/req_txt/req_47.txt) | configuration selection | [feature_model_9](./benchmark/json/feature_model_cost_9.json) | [feature_model_constraint_9.json](./benchmark/json/feature_model_constraint_9.json) | None |
| [48](./requirements/req_txt/req_48.txt) | configuration prioritization | [feature_model_9](./benchmark/json/feature_model_cost_9.json) | [feature_model_constraint_9.json](./benchmark/json/feature_model_constraint_9.json) | 1 |
| [49](./requirements/req_txt/req_49.txt) | configuration prioritization | [feature_model_9](./benchmark/json/feature_model_cost_9.json) | [feature_model_constraint_9.json](./benchmark/json/feature_model_constraint_9.json) | 5 |
| [50](./requirements/req_txt/req_50.txt) | configuration selection | [feature_model_10](./benchmark/json/feature_model_cost_10.json) | [feature_model_constraint_10.json](./benchmark/json/feature_model_constraint_10.json) | None |
| [51](./requirements/req_txt/req_51.txt) | configuration prioritization | [feature_model_10](./benchmark/json/feature_model_cost_10.json) | [feature_model_constraint_10.json](./benchmark/json/feature_model_constraint_10.json) | 1 |
| [52](./requirements/req_txt/req_52.txt) | configuration prioritization | [feature_model_10](./benchmark/json/feature_model_cost_10.json) | [feature_model_constraint_10.json](./benchmark/json/feature_model_constraint_10.json) | 5 |
| [53](./requirements/req_txt/req_53.txt) | configuration selection | [feature_model_11](./benchmark/json/feature_model_cost_11.json) | [feature_model_constraint_11.json](./benchmark/json/feature_model_constraint_11.json) | None |
| [54](./requirements/req_txt/req_54.txt) | configuration prioritization | [feature_model_11](./benchmark/json/feature_model_cost_11.json) | [feature_model_constraint_11.json](./benchmark/json/feature_model_constraint_11.json) | 1 |
| [55](./requirements/req_txt/req_55.txt) | configuration prioritization | [feature_model_11](./benchmark/json/feature_model_cost_11.json) | [feature_model_constraint_11.json](./benchmark/json/feature_model_constraint_11.json) | 5 |
| [56](./requirements/req_txt/req_56.txt) | configuration selection | [feature_model_12](./benchmark/json/feature_model_cost_12.json) | [feature_model_constraint_12.json](./benchmark/json/feature_model_constraint_12.json) | None |
| [57](./requirements/req_txt/req_57.txt) | configuration prioritization | [feature_model_12](./benchmark/json/feature_model_cost_12.json) | [feature_model_constraint_12.json](./benchmark/json/feature_model_constraint_12.json) | 1 |
| [58](./requirements/req_txt/req_58.txt) | configuration prioritization | [feature_model_12](./benchmark/json/feature_model_cost_12.json) | [feature_model_constraint_12.json](./benchmark/json/feature_model_constraint_12.json) | 5 |
| [59](./requirements/req_txt/req_59.txt) | configuration selection | [feature_model_13](./benchmark/json/feature_model_cost_13.json) | [feature_model_constraint_13.json](./benchmark/json/feature_model_constraint_13.json) | None |
| [60](./requirements/req_txt/req_60.txt) | configuration prioritization | [feature_model_13](./benchmark/json/feature_model_cost_13.json) | [feature_model_constraint_13.json](./benchmark/json/feature_model_constraint_13.json) | 1 |
| [61](./requirements/req_txt/req_61.txt) | configuration prioritization | [feature_model_13](./benchmark/json/feature_model_cost_13.json) | [feature_model_constraint_13.json](./benchmark/json/feature_model_constraint_13.json) | 5 |
| [62](./requirements/req_txt/req_62.txt) | configuration selection | [feature_model_14](./benchmark/json/feature_model_cost_14.json) | [feature_model_constraint_14.json](./benchmark/json/feature_model_constraint_14.json) | None |
| [63](./requirements/req_txt/req_63.txt) | configuration prioritization | [feature_model_14](./benchmark/json/feature_model_cost_14.json) | [feature_model_constraint_14.json](./benchmark/json/feature_model_constraint_14.json) | 1 |
| [64](./requirements/req_txt/req_64.txt) | configuration prioritization | [feature_model_14](./benchmark/json/feature_model_cost_14.json) | [feature_model_constraint_14.json](./benchmark/json/feature_model_constraint_14.json) | 5 |
| [65](./requirements/req_txt/req_65.txt) | configuration selection | [feature_model_15](./benchmark/json/feature_model_cost_15.json) | [feature_model_constraint_15.json](./benchmark/json/feature_model_constraint_15.json) | None |
| [66](./requirements/req_txt/req_66.txt) | configuration prioritization | [feature_model_15](./benchmark/json/feature_model_cost_15.json) | [feature_model_constraint_15.json](./benchmark/json/feature_model_constraint_15.json) | 1 |
| [67](./requirements/req_txt/req_67.txt) | configuration prioritization | [feature_model_15](./benchmark/json/feature_model_cost_15.json) | [feature_model_constraint_15.json](./benchmark/json/feature_model_constraint_15.json) | 5 |
| [68](./requirements/req_txt/req_68.txt) | configuration selection | [feature_model_16](./benchmark/json/feature_model_cost_16.json) | [feature_model_constraint_16.json](./benchmark/json/feature_model_constraint_16.json) | None |
| [69](./requirements/req_txt/req_69.txt) | configuration prioritization | [feature_model_16](./benchmark/json/feature_model_cost_16.json) | [feature_model_constraint_16.json](./benchmark/json/feature_model_constraint_16.json) | 1 |
| [70](./requirements/req_txt/req_70.txt) | configuration prioritization | [feature_model_16](./benchmark/json/feature_model_cost_16.json) | [feature_model_constraint_16.json](./benchmark/json/feature_model_constraint_16.json) | 5 |
| [71](./requirements/req_txt/req_71.txt) | configuration selection | [feature_model_17](./benchmark/json/feature_model_cost_17.json) | [feature_model_constraint_17.json](./benchmark/json/feature_model_constraint_17.json) | None |
| [72](./requirements/req_txt/req_72.txt) | configuration prioritization | [feature_model_17](./benchmark/json/feature_model_cost_17.json) | [feature_model_constraint_17.json](./benchmark/json/feature_model_constraint_17.json) | 1 |
| [73](./requirements/req_txt/req_73.txt) | configuration prioritization | [feature_model_17](./benchmark/json/feature_model_cost_17.json) | [feature_model_constraint_17.json](./benchmark/json/feature_model_constraint_17.json) | 5 |
| [74](./requirements/req_txt/req_74.txt) | configuration selection | [feature_model_18](./benchmark/json/feature_model_cost_18.json) | [feature_model_constraint_18.json](./benchmark/json/feature_model_constraint_18.json) | None |
| [75](./requirements/req_txt/req_75.txt) | configuration prioritization | [feature_model_18](./benchmark/json/feature_model_cost_18.json) | [feature_model_constraint_18.json](./benchmark/json/feature_model_constraint_18.json) | 1 |
| [76](./requirements/req_txt/req_76.txt) | configuration prioritization | [feature_model_18](./benchmark/json/feature_model_cost_18.json) | [feature_model_constraint_18.json](./benchmark/json/feature_model_constraint_18.json) | 5 |
| [77](./requirements/req_txt/req_77.txt) | configuration selection | [feature_model_19](./benchmark/json/feature_model_cost_19.json) | [feature_model_constraint_19.json](./benchmark/json/feature_model_constraint_19.json) | None |
| [78](./requirements/req_txt/req_78.txt) | configuration prioritization | [feature_model_19](./benchmark/json/feature_model_cost_19.json) | [feature_model_constraint_19.json](./benchmark/json/feature_model_constraint_19.json) | 1 |
| [79](./requirements/req_txt/req_79.txt) | configuration prioritization | [feature_model_19](./benchmark/json/feature_model_cost_19.json) | [feature_model_constraint_19.json](./benchmark/json/feature_model_constraint_19.json) | 5 |

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
