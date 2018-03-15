#!/usr/bin/env python2

import sys, os, re, json, subprocess
from klab.process import tee
from . import pipeline

def submit(script, workspace, **params):
    """Submit a job with the given parameters."""
    from klab import cluster, process

    # Make sure the rosetta symlink has been created.

    if not os.path.exists(workspace.rosetta_dir):
        raise pipeline.RosettaNotFound(workspace)

    # Parse some job parameters for the keyword arguments.

    params = dict((k, v) for k, v in params.items() if v is not None)
    test_run = params.get('test_run', False)
    nstruct = params.get('nstruct')
    max_runtime = params.get('max_runtime', '6:00:00')
    max_memory = params.get('max_memory', '1G')

    if test_run:
        nstruct = 50

    if nstruct is None:
        raise TypeError("submit() requires the keyword argument 'nstruct' for production runs.")

    # Submit the job and put it immediately into the hold state.

    qsub_command = 'qsub', '-h', '-cwd'
    qsub_command += '-o', workspace.stdout_dir
    qsub_command += '-e', workspace.stderr_dir
    qsub_command += '-t', '1-{0}'.format(nstruct),
    qsub_command += '-l', 'h_rt={0}'.format(max_runtime),
    qsub_command += '-l', 'mem_free={0}'.format(max_memory),
    qsub_command += pipeline.big_job_path(script),
    qsub_command += workspace.focus_dir,

    status = process.check_output(qsub_command)
    status_pattern = re.compile(r'Your job-array (\d+).[0-9:-]+ \(".*"\) has been submitted')
    status_match = status_pattern.match(status)

    if not status_match:
        print status
        sys.exit()

    # Figure out the job id, then make a params file specifically for it.

    job_id = status_match.group(1)

    with open(workspace.job_info_path(job_id), 'w') as file:
        json.dump(params, file)

    # Release the hold on the job.

    qrls_command = 'qrls', job_id
    process.check_output(qrls_command)
    print status,

def initiate():
    """Return some relevant information about the currently running job."""
    print_debug_header()

    workspace = pipeline.workspace_from_dir(sys.argv[1])
    workspace.cd_to_root()

    job_info = read_job_info(workspace.job_info_path(os.environ['JOB_ID']))
    job_info['job_id'] = int(os.environ['JOB_ID'])
    job_info['task_id'] = int(os.environ['SGE_TASK_ID']) - 1

    return workspace, job_info

def debrief():
    """
    Report the amount of memory used by this job, among other things.
    """
    job_number = os.environ['JOB_ID'] + '.' + os.environ['SGE_TASK_ID']
    run_command(['/usr/local/sge/bin/linux-x64/qstat', '-j', job_number])

def run_rosetta(workspace, job_info, 
        use_resfile=False, use_restraints=False, use_fragments=False):

    test_run = job_info.get('test_run', False)
    rosetta_cmd = [
        workspace.rosetta_scripts_path,
        '-database', workspace.rosetta_database_path,
        '-in:file:s', workspace.input_path(job_info),
        '-in:file:native', workspace.input_path(job_info),
        '-out:prefix', workspace.output_prefix(job_info),
        '-out:suffix', workspace.output_suffix(job_info),
        '-out:no_nstruct_label',
        '-out:overwrite',
        '-out:pdb_gz',
        '-out:mute', 'protocols.loops.loops_main',
        '-parser:protocol', workspace.protocol_path,
        '-parser:script_vars',
            'wts_file=' + workspace.scorefxn_path,
            'cst_file=' + workspace.restraints_path,
            'loop_file=' + workspace.loops_path,
            'loop_start=' + str(workspace.loop_boundaries[0]),
            'loop_end=' + str(workspace.loop_boundaries[1]),
            'outputs_folder=' + workspace.seqprof_dir,
            'design_number=' + workspace.output_basename(job_info),
            'vall_path=' + workspace.rosetta_vall_path(test_run),
            'fragment_weights=' + workspace.fragment_weights_path,
            'fast=' + ('yes' if test_run else 'no'),
    ]
    if use_resfile: rosetta_cmd += [
        '-packing:resfile', workspace.resfile_path,
    ]
    if use_restraints: rosetta_cmd += [
        '-constraints:cst_fa_file', workspace.restraints_path,
    ]
    if use_fragments: rosetta_cmd += \
        workspace.fragments_flags(workspace.input_path(job_info))

    rosetta_cmd += [
        '@', workspace.flags_path,
    ]

    run_command(rosetta_cmd)
    run_external_metrics(workspace, job_info)

def run_external_metrics(workspace, job_info):
    pdb_path = workspace.output_path(job_info)

    for metric in workspace.metric_scripts:
        stdout, stderr = run_command([metric, pdb_path])

        with open(pdb_path, 'a') as file:
            file.write('EXTRA_METRIC ' + stdout)
            
def run_command(command):
    print "Working directory:", os.getcwd()
    print "Command:", ' '.join(command)
    sys.stdout.flush()

    return tee(command)

def read_job_info(json_path):
    with open(json_path) as file:
        return json.load(file)

def print_debug_header():
    from datetime import datetime
    from socket import gethostname

    print "Date:", datetime.now()
    print "Host:", gethostname()
    print "Python:", sys.executable or 'unknown!'
    print "Command: JOB_ID={0[JOB_ID]} SGE_TASK_ID={0[SGE_TASK_ID]} {1}".format(
            os.environ, ' '.join(sys.argv))
    print
    sys.stdout.flush()


    
