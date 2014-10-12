#!/usr/bin/env python2

def submit(script, workspace, **params):
    # Assume that the script accepts exactly two command-line arguments: the 
    # name of a workspace and (optionally) whether or not to do a test run.

    import re, sys, json, subprocess
    from tools import cluster, process

    params = dict((k, v) for k, v in params.items() if v is not None)
    test_run = params.get('test_run', False)
    nstruct = params.get('nstruct', 50 if test_run else None)
    max_runtime = params.get('max_runtime', '0:30:' if test_run else '6:00:')

    if nstruct is None:
        raise TypeError("qsub() requires the keyword argument 'nstruct' for production runs.")

    with open(workspace.params_path, 'w') as file:
        json.dump(params, file)

    qsub_command = 'qsub', '-h'
    qsub_command += '-o', workspace.stdout_dir, '-e', workspace.stderr_dir,
    qsub_command += '-t', '1-{0}'.format(nstruct),
    qsub_command += '-l', 'h_rt={0}'.format(max_runtime),
    qsub_command += 'workhorses/kr_build.py', workspace.name,

    status = process.check_output(qsub_command)
    status_pattern = re.compile(r'Your job-array (\d+).[0-9:-]+ \(".*"\) has been submitted')
    status_match = status_pattern.match(status)

    if not status_match:
        print status
        sys.exit()

    job_id = status_match.group(1)
    qrls_command = 'qrls', job_id
    subprocess.call(qrls_command)

    print status

def get_parameters(workplace_factory):
    import sys

    workspace = workplace_factory(*sys.argv[1:])
    job_id = int(os.environ['JOB_ID'])
    task_id = int(os.environ['SGE_TASK_ID']) - 1

    with open(workspace.params_path) as file:
        parameters = json.load(file)

    return workspace, job_id, task_id, parameters

    

