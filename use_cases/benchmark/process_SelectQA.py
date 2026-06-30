# This script processes the original data from the SIR programs to
# create JSON files containing the objectives for each test case, which will be used in the SelectQA.

# -----------------------------------------------------------------

# Resued code from the previous project, with some modifications to adapt it to the new one
# Original repository: https://github.com/AntonioTrovato/SelectQA
# Original file path: MOQ-Pipeline.ipynb

# -----------------------------------------------------------------

#this cell contains all the imports needed by the pipeline
#to run it on the browser: jupyter notebook --NotebookApp.iopub_data_rate_limit=1.0e10
import json
import os
import yaml

#this cell contains all variable definitions that will be useful throughout the entire project
sir_programs_tests_number = {"flex":567,"grep":806,"gzip":214,"sed":360}
sir_programs_end_lines = {"flex":14192,"grep":13281,"gzip":6701,"sed":7118}
alpha = 0.5
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_DIR = os.path.join(DIRECTORY, "original")
JSON_DIR = os.path.join(DIRECTORY, "json")
YAML_CONFIG_PATH = os.path.join(os.path.dirname(DIRECTORY), "config.yaml")
with open(YAML_CONFIG_PATH, "r", encoding="utf-8") as yaml_file:
    config = yaml.safe_load(yaml_file)
SIR_PROGRAMS = config["SelectQA_bench"]
#let's make a function to read the fault matrices
#IMPORTANT: all the fault-matrix files must be renamed as "fault-matrix".txt and must be written using the same standard used by the files of this project (i-th line->e0e1e2e3..., where ej is 0 if the i-th test found a bug when launched on the j-th version)
def get_fault_list(program_name:str):
    """This function opens the fault-matrix file of a sir programs and makes a list of binary values for each test case of that program to indicate whether a test case found or not a bug in at least one of the available versions of the program"""
    #open the fault-matrix file of the desired SIR program
    fault_matrix_path = os.path.join(ORIGINAL_DIR, program_name, "fault-matrix.txt")
    with open(fault_matrix_path, encoding="utf-8") as program_file:
        lines = program_file.readlines()
    
    #we need a list which elements represent test cases, the i-th element is 1 if the i-th test case
    #discovered a fault in the past, 0 otherwise
    faults_test_by_test = list()
    
    i = 0
    for line in lines:
        if "1" in line:
            faults_test_by_test.append(1)
        else:
            faults_test_by_test.append(0)
        i += 1
    
    return faults_test_by_test

#the next function is able to research into the json coverage information file of each test case
#of each sir program to gather information about the single test cases costs and coverage
def cost_and_coverage_information_gathering(program_name:str):
    """The aim of this function is to obtain a dictionary that for each test case of a program indicates its cost, and a dictionary that, for each code line of the program to test, makes a list of all the test cases that run that line"""
    test_case_execution_cost = 0
    
    execution_cost_test_by_test = dict()
    executed_lines_test_by_test = dict()
    lines_of_tests_list = dict()
    total_file_lines = 0
    read_files = []
    
    for test_case in range(sir_programs_tests_number[program_name]):
        #to open the correct file, we must remember that the folders and the json files are
        #numbered from 1 and not from 0
        if program_name == "gzip":
            json_name = "allfile"
        else:
            json_name = program_name
        test_case_json_path = os.path.join(
            ORIGINAL_DIR,
            program_name,
            f"json_{program_name}",
            f"t{test_case + 1}",
            f"{json_name}{test_case + 1}.gcov.json",
        )
        with open(test_case_json_path, encoding="utf-8") as test_case_json:
            #read the JSON object as a dictionary
            json_data = json.load(test_case_json)
        
        # to have coverage % we will need the total number of lines to cover
        for file in json_data["files"]:
            if file["file"] not in read_files:
                total_file_lines += len(file["lines"])
                read_files.append(file["file"])
        
        #for programs tested above more than one file, the initial row of a file will start from
        #the final row of the preceding file
        i = 0
        for file in json_data["files"]:
            line_count_start = i
            for line in file["lines"]:
                #if a line is executed, we want to remember FOR THAT LINE which are the tests
                #that executed it, and we want to increment the execution cost
                if line["unexecuted_block"] == False:
                    #the test suite exec cost = sum of the exec freq. of each executed basic block
                    #by each test case
                    #test_suite_execution_cost += line["count"]
                    test_case_execution_cost += line["count"]
                    
                    if (line_count_start + line["line_number"]) not in executed_lines_test_by_test:
                        executed_lines_test_by_test[line_count_start + line["line_number"]] = [test_case]
                    else:
                        executed_lines_test_by_test[line_count_start + line["line_number"]].append(test_case)
                    executed_lines_test_by_test[line_count_start + line["line_number"]].sort()
                    
                    if test_case not in lines_of_tests_list:
                        lines_of_tests_list[test_case] = [line_count_start + line["line_number"]]
                    else:
                        lines_of_tests_list[test_case].append(line_count_start + line["line_number"])
                    lines_of_tests_list[test_case].sort()
                i = line["line_number"]
        
        #saving the total amount of execution cost for this test case and resetting for the next
        execution_cost_test_by_test[test_case] = test_case_execution_cost
        test_case_execution_cost = 0
        
    return execution_cost_test_by_test, executed_lines_test_by_test, lines_of_tests_list, total_file_lines

def save_program_objectives(
    program_name: str,
    execution_cost_test_by_test: dict,
    lines_of_tests_by_test: dict,
    faults_test_by_test: list,
):
    """Save the three objective values of each test case into ./json/{program_name}.json."""
    os.makedirs(JSON_DIR, exist_ok=True)

    program_objectives = []
    for test_case in range(sir_programs_tests_number[program_name]):
        program_objectives.append({
            "id": f"t{test_case}",
            "statement_cov": len(lines_of_tests_by_test.get(test_case, [])),
            "execution_cost": execution_cost_test_by_test.get(test_case, 0),
            "faults_cov": faults_test_by_test[test_case],
        })

    output_path = os.path.join(JSON_DIR, f"{program_name}.json")
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(program_objectives, output_file, indent=2)

    return output_path

def main():
    #we can now gain all the historical information about past fault detection
    faults_dictionary = {"flex": None, "grep": None, "gzip": None, "sed": None}

    for sir_program in SIR_PROGRAMS:
        faults_dictionary[sir_program] = get_fault_list(sir_program) # type: ignore

    #we can now gain costs and coverage information

    test_cases_costs = {"flex":None,"grep":None,"gzip":None,"sed":None}
    coverage = {"flex":None,"grep":None,"gzip":None,"sed":None}
    lines_of_tests_list = {"flex":None,"grep":None,"gzip":None,"sed":None}
    total_file_lines = {"flex":None,"grep":None,"gzip":None,"sed":None}

    for sir_program in SIR_PROGRAMS:
        costs_and_coverage = cost_and_coverage_information_gathering(sir_program)
        test_cases_costs[sir_program] = costs_and_coverage[0]       # type: ignore
        coverage[sir_program] = costs_and_coverage[1]               # type: ignore
        lines_of_tests_list[sir_program] = costs_and_coverage[2]    # type: ignore
        total_file_lines[sir_program] = costs_and_coverage[3]       # type: ignore
        output_path = save_program_objectives(
            sir_program,
            test_cases_costs[sir_program],      # type: ignore
            lines_of_tests_list[sir_program],   # type: ignore
            faults_dictionary[sir_program],     # type: ignore
        )
        print(f"Saved {sir_program} objectives to {output_path}")

if __name__ == "__main__":
    main()
