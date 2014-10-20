#!/usr/bin/env python2

import sys, os, re, json, subprocess
from . import pipeline

def submit(script, workspace, **params):
    from tools import cluster, process

    # Parse some parameters that 
    params = dict((k, v) for k, v in params.items() if v is not None)
    test_run = params.get('test_run', False)
    nstruct = params.get('nstruct')
    max_runtime = params.get('max_runtime', '6:00:00')
    max_memory = params.get('max_runtime', '1G')

    if test_run:
        nstruct = 50
        max_runtime = '0:30:00'

    if nstruct is None:
        raise TypeError("qsub() requires the keyword argument 'nstruct' for production runs.")

    qsub_command = 'qsub', '-h'
    qsub_command += '-o', workspace.stdout_dir, '-e', workspace.stderr_dir,
    qsub_command += '-t', '1-{0}'.format(nstruct),
    qsub_command += '-l', 'h_rt={0}'.format(max_runtime),
    qsub_command += '-l', 'memfree={0}'.format(max_memory),
    qsub_command += pipeline.big_job_path(script), workspace.focus_dir,

    status = process.check_output(qsub_command)
    status_pattern = re.compile(r'Your job-array (\d+).[0-9:-]+ \(".*"\) has been submitted')
    status_match = status_pattern.match(status)

    if not status_match:
        print status
        sys.exit()

    job_id = status_match.group(1)

    with open(workspace.job_params_path(job_id), 'w') as file:
        json.dump(params, file)

    qrls_command = 'qrls', job_id
    process.check_output(qrls_command)
    print status,

def initiate():
    workspace = pipeline.workspace_from_dir(sys.argv[1])
    job_id = int(os.environ['JOB_ID'])
    task_id = int(os.environ['SGE_TASK_ID']) - 1
    job_params = read_params(workspace.job_params_path(job_id))

    return workspace, job_id, task_id, job_params

def read_params(params_path):
    with open(params_path) as file:
        return json.load(file)


