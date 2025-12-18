import flask
import json
import os
import sys
import time
import vyg
from flask import current_app as app

def escape_field(field:str):
    return field.replace('\n', '\\n').replace('\t', '\\t')

def unescape_field(field:str):
    return field.replace('\\n', '\n').replace('\\t', '\t')

def log_event2(fields):
    '''' Log an entry '''
    timestamp = time.strftime('%y%m%d\t%H%M%S')
    user_obj = flask.session.get('user')
    username = user_obj.get('email', '') if user_obj else ''
    request = flask.request
    # date time ip scheme url status_code user body fields
    log_file = os.path.join(app.config.get('DATA_FOLDER'), 'vyg.tsv')
    with open(log_file, 'a', encoding='utf8') as log_file:
        log_file.write(f'{timestamp}\t{request.remote_addr}\t{request.method}\t'
            f'{request.url}\t{username}\t{fields}\n')

def vyg_log(action, value=None):
    """ Log an info event with the given fields """
    text = ''
    if value is not None:
        if isinstance(value, str):
            text = escape_field(value)
        elif isinstance(value, dict):
            text = escape_field(vyg.to_json(value))
    info = action
    if text:
        info += '\t' + text
    log_event2(info)

def extract_log(log_file:str, output_folder: str):
    """ Extract the log file for download """
    if not os.path.exists(log_file):
        raise FileNotFoundError(f'Log file not found: {log_file}')
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    # For each line of the log file
    with open(log_file, 'r', encoding='utf8') as log_file:
        line_number = 0
        for line in log_file:
            line_number += 1
            try:
                extract_line(line_number, line, output_folder)
            except Exception as e:
                print(f'Error processing line {line_number}: {e}')
                raise e

def extract_line(line_number:int, line:str, output_folder: str):
    """ Extract a line of the log file """
    line = line.strip()
    if len(line) == 0:
        # Ignore empty lines
        return
    parts = line.split('\t')
    if len(parts) != 8:
        raise ValueError(f'Line {line_number} has {len(parts)} fields instead of 8: {line}')
    for index, field in enumerate(parts):
        parts[index] = unescape_field(field)
    log_entry = {}
    log_entry['yymmdd'] = parts[0]
    log_entry['hhmmss'] = parts[1]
    log_entry['ip_addr'] = parts[2]
    log_entry['req_method'] = parts[3]
    log_entry['url'] = parts[4]
    log_entry['username'] = parts[5] if len(parts[5]) > 0 else 'anonymous'
    log_entry['action'] = parts[6]
    log_entry['data'] = parts[7]
    extract_entry(log_entry, output_folder)

def extract_entry(log_entry:dict, output_folder: str):
    """ Extract a single log entry """
    # Create a folder for user if it does not exist
    username = log_entry.get('username', 'anonymous')
    user_folder = os.path.join(output_folder, username)
    os.makedirs(user_folder, exist_ok=True)
    user_logname = os.path.join(user_folder, f'{username}.tsv')
    # Inside the user folder, create a entry for the events of this user
    if not os.path.exists(user_logname):
        # Create header
        with open(user_logname, 'w', encoding='utf8') as user_log_file:
            user_log_file.write('yymmdd\thhmmss\tip_addr\treq_method\turl\taction\tdata\n')
    # actions: visit, login, logout, run, run_submission, run_result
    action = log_entry.get('action', '')
    # Export the event to the user log file if it is not a run submission
    if action == 'run_submission':
        extract_submission(log_entry, user_folder)
        log_entry['data'] = '(extracted)'
    elif action == 'run_result':
        extract_run_result(log_entry, user_folder)
        log_entry['data'] = '(extracted)'
    # Append the log entry to the user log file
    with open(user_logname, 'a', encoding='utf8') as user_log_file:
        user_log_file.write(f'{log_entry["yymmdd"]}\t{log_entry["hhmmss"]}'
            f'\t{log_entry["ip_addr"]}\t{log_entry["req_method"]}\t{log_entry["url"]}'
            f'\t{log_entry["action"]}\t{log_entry["data"]}\n')

# Extracted folder:
# u22/
#    prime_counter/
#        readme.html
#        tests/
#            input001.txt
#            output001.txt
#        initial/
#            solution.cpp
#        src-230101_123456/
#            solution.cpp
#            run-230101_123460.tsv
#            failed/
#                output002.txt
#        src -> src-230101_123456

def extract_submission(log_entry:dict, user_folder: str):
    """ Export a run submission or result to a folder with files """
    # Data field is a submission in JSON format
    submission = json.loads(log_entry['data'])
    # Problem name is not in JSON object because a bug, get if from last part of URL
    problem_name = log_entry.get('url', '').split('/')[-1]
    # Submission has two parts, the problem and the solution
    # Extract the problem if not already done
    problem = vyg.Problem(submission.get('problem', {}), None, True)
    problem_folder = os.path.join(user_folder, problem_name)
    # Create a folder for this submission using the problem name and timestamp
    if not os.path.exists(problem_folder):
        os.makedirs(problem_folder, exist_ok=True)
        extract_problem(problem, problem_folder)
    solution = vyg.Message(submission.get('solution', {}))
    extract_solution(log_entry, solution, problem_folder)

# Submission example:
# {
#   "problem": {
#     "title": "base64encoded",
#     "overdue_policy": "disabled",
#     "weight": 1.0,
#     "statement": "base64encoded",
#     "tests": [
#       {
#         "input": "base64encoded=",
#         "output": "base64encoded=",
#         "points": 1,
#         "minThreads": 1,
#         "maxThreads": 32768
#       },
#     ],
#     "languages": [
#       "C++"
#     ],
#     "initialCodeFor": {
#       "C++": "base64encoded"
#     },
#     "maxThreads": 32768,
#     "allowIndeterminism": "none",
#     "maxDuration": 1.0,
#     "tools": "tsan lint",
#     "folder_loaded": true
#   },
#   "solution": {
#     "action": "run",
#     "language": "C++",
#     "code": "base64encoded"
#   }
# }

def extract_problem(problem:vyg.Problem, problem_folder: str):
    """ Export a problem to a folder with files """
    extract_file(problem_folder, 'readme.html', problem.statement)
    extract_file(problem_folder, 'Makefile', 'include ~/dev/ucr/Makefile\n')
    # Export all test cases
    test_folder = os.path.join(problem_folder, 'tests')
    tests = problem.tests
    if len(tests) > 0:
        os.makedirs(test_folder, exist_ok=True)
        for index, test in enumerate(tests):
            # Use three leading zeros for test case number
            test_number = f'{index + 1:03d}'
            extract_file(test_folder, f'args{test_number}.txt', test.commandLineArguments)
            extract_file(test_folder, f'input{test_number}.txt', test.input)
            extract_file(test_folder, f'output{test_number}.txt', test.output)
            extract_file(test_folder, f'stderr{test_number}.txt', test.stderr)
    # Export initial code for each language
    for language, initial_code in problem.initialCodeFor.items():
        initial_folder = os.path.join(problem_folder, 'initial')
        os.makedirs(initial_folder, exist_ok=True)
        extract_file(initial_folder, f'solution.{vyg.EXTENSION_LANGUAGES[language]}', initial_code)

def extract_solution(log_entry:dict, solution:vyg.Message, problem_folder: str):
    """ Export a solution to a folder with files """
    # Create a folder for this solution if it does not exist
    timestamp = f'{log_entry["yymmdd"]}_{log_entry["hhmmss"]}'
    solution_folder = os.path.join(problem_folder, f'src-{timestamp}')
    os.makedirs(solution_folder, exist_ok=True)
    # Create a folder for this solution using the timestamp
    # Export the code file
    filename = f'solution.{vyg.EXTENSION_LANGUAGES.get(solution.language, "txt")}'
    extract_file(solution_folder, filename, solution.code)
    # Create or update the src symlink to point to the latest solution
    src_link = os.path.join(problem_folder, 'src')
    if os.path.islink(src_link) or os.path.exists(src_link):
        os.remove(src_link)
    os.symlink(os.path.basename(solution_folder), src_link)

# run_result example:
# {
#   "status": "runtimeError",
#   "passedTestCount": 2,
#   "points": 2,
#   "totalPoints": 2,
#   "maxWallTime": 1.0,
#   "results": [
#     {
#       "status": "passed",
#       "stdout": "MiBwcmltZXM6CjcKMg==",
#       "wallTime": 0.02
#     },
#     {
#       "status": "runtimeError",
#       "message": "RXhpdCBjb2RlIDEyNA==",
#       "exitCode": 124,
#       "wallTime": 1.0
#     },
#   ]
# }

def extract_run_result(log_entry:dict, user_folder: str):
    """ Export a run result to a folder with files """
    # Data field is a run result in JSON format
    result = json.loads(log_entry['data'])
    # Problem name is not in JSON object because a bug, get if from last part of URL
    problem_name = log_entry.get('url', '').split('/')[-1]
    # Create a folder for this result using the problem name and timestamp
    run_folder = os.path.join(user_folder, problem_name, 'src')
    timestamp = f'{log_entry["yymmdd"]}_{log_entry["hhmmss"]}'
    # Export the run result to a TSV file
    run_tsv = os.path.join(run_folder, f'run-{timestamp}.tsv')
    with open(run_tsv, 'w', encoding='utf8') as run_file:
        run_file.write('test\tstatus\texit_code\twall_time\tmessage\n')
        results = result.get('results', [])
        for index1, test_result in enumerate(results, 1):
            status = test_result.get('status', '')
            wall_time = test_result.get('wallTime', -0.0)
            message = vyg.decode(unescape_field(test_result.get('message', '')))
            stdout = vyg.decode(unescape_field(test_result.get('stdout', '')))
            exit_code = test_result.get('exitCode', '')
            run_file.write(f'{index1}\t{status}\t{exit_code}\t{wall_time}\t{message}\n')
            # If user failed this test, export the output to a file
            if status != 'passed' and stdout:
                failed_folder = os.path.join(run_folder, 'failed')
                os.makedirs(failed_folder, exist_ok=True)
                test_number = f'{index1:03d}'
                extract_file(failed_folder, f'output{test_number}.txt', stdout)

def extract_file(folder:str, filename:str, content:str):
    """ Export a file to a folder with given content """
    if content:
        file_path = os.path.join(folder, filename)
        with open(file_path, 'w', encoding='utf8') as file:
            file.write(content)

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        # log_file = os.path.join(app.config.get('DATA_FOLDER'), 'vyg.tsv')
        extract_log(sys.argv[1], sys.argv[2])
    else:
        print('Usage: python vyg_log.py log_file output_folder')
