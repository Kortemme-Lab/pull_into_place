#!/usr/bin/env python2

def submit(script, workspace, **params):
    # Assume that the script accepts exactly two command-line arguments: the 
    # name of a workspace and (optionally) whether or not to do a test run.

    import json, subprocess
    from tools import cluster

    cluster.require_chef()

    test_run = params.get('test_run', False)
    nstruct = params.get('nstruct', 50 if test_run else None)
    max_runtime = params.get('max_runtime', '0:30:' if test_run else '6:00:')

    if nstruct is None:
        raise TypeError("qsub() requires the keyword argument 'nstruct' for production runs.")

    with open(workspace.params_path, 'w') as file:
        json.dump(params, file)

    qsub_command = 'qsub',
    qsub_command += '-o', workspace.stdout_dir, '-e', workspace.stderr_dir,
    qsub_command += '-t', '1-{}'.format(nstruct),
    qsub_command += '-l', 'h_rt={}'.format(max-runtime),
    qsub_command += 'workhorses/kr_build.py', workspace.name, test_run,

    subprocess.call(qsub_command)

def get_parameters(workplace_factory):
    import sys

    workspace = workplace_factory(*sys.argv[1:])
    job_id = int(os.environ['JOB_ID'])
    task_id = int(os.environ['SGE_TASK_ID']) - 1

    with open(workspace.params_path) as file:
        parameters = json.load(file)

    return workspace, job_id, task_id, parameters

    

