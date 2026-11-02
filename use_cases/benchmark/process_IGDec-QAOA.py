# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

# This script processes the original data from the IGDec-QAOA benchmarks to
# create JSON files containing the objectives for each test case.

# -----------------------------------------------------------------

#this cell contains all the imports needed by the pipeline
import csv
import json
import os
import yaml

#this cell contains all variable definitions that will be useful throughout the entire project
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_DIR = os.path.join(DIRECTORY, "original")
JSON_DIR = os.path.join(DIRECTORY, "json")
YAML_CONFIG_PATH = os.path.join(os.path.dirname(DIRECTORY), "config.yaml")
with open(YAML_CONFIG_PATH, "r", encoding="utf-8") as yaml_file:
    config = yaml.safe_load(yaml_file)
BENCHMARKS = config["IGDecQAOA_bench"]
SPECIAL_BENCHMARKS = [
    "elevator_o2", "elevator_o3"
]  # Benchmarks with different objective structures

def read_csv_rows(program_name:str):
    """This function opens the csv file of a benchmark and returns all rows."""
    program_file_path = os.path.join(ORIGINAL_DIR, f"{program_name}.csv")
    with open(program_file_path, encoding="utf-8") as program_file:
        csv_reader = csv.DictReader(program_file)
        rows = list(csv_reader)

    return rows

def save_time_rate_objectives(program_name:str):
    """Save the time and rate objective values of each test case into ./json/{program_name}.json."""
    os.makedirs(JSON_DIR, exist_ok=True)

    rows = read_csv_rows(program_name)
    program_objectives = []
    for test_case, row in enumerate(rows):
        program_objectives.append({
            "id": f"t{test_case}",
            "time": float(row["time"]),
            "rate": float(row["rate"]),
        })

    output_path = os.path.join(JSON_DIR, f"{program_name}.json")
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(program_objectives, output_file, indent=2)

    return output_path

def save_elevator_o2_objectives():
    """Save the cost and input_div objective values of each elevator test case into ./json/elevator_o2.json."""
    os.makedirs(JSON_DIR, exist_ok=True)

    rows = read_csv_rows("elevator")
    program_objectives = []
    for test_case, row in enumerate(rows):
        program_objectives.append({
            "id": f"t{test_case}",
            "cost": int(row["cost"]),
            "input_div": float(row["input_div"]),
        })

    output_path = os.path.join(JSON_DIR, "elevator_o2.json")
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(program_objectives, output_file, indent=2)

    return output_path

def save_elevator_o3_objectives():
    """Save the cost, pcount and dist objective values of each elevator test case into ./json/elevator_o3.json."""
    os.makedirs(JSON_DIR, exist_ok=True)

    rows = read_csv_rows("elevator")
    program_objectives = []
    for test_case, row in enumerate(rows):
        program_objectives.append({
            "id": f"t{test_case}",
            "cost": int(row["cost"]),
            "pcount": int(row["pcount"]),
            "dist": int(row["dist"]),
        })

    output_path = os.path.join(JSON_DIR, "elevator_o3.json")
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(program_objectives, output_file, indent=2)

    return output_path

def main():
    for program in BENCHMARKS:
        if program in SPECIAL_BENCHMARKS:
            continue
        output_path = save_time_rate_objectives(program)
        print(f"Saved {program} objectives to {output_path}")

    output_path = save_elevator_o2_objectives()
    print(f"Saved elevator_o2 objectives to {output_path}")

    output_path = save_elevator_o3_objectives()
    print(f"Saved elevator_o3 objectives to {output_path}")

if __name__ == "__main__":
    main()
