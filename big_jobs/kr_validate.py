#!/usr/bin/env python2

#$ -S /usr/bin/python
#$ -l mem_free=1G
#$ -l arch=linux-x64
#$ -l netapp=1G
#$ -cwd

import os, sys; sys.path.append(os.getcwd())
import subprocess
from libraries import big_job

workspace, job_id, task_id, parameters = big_job.initiate()

designs = parameters['inputs']
input_path = designs[task_id % len(designs)]
output_subdir = workspace.output_subdir(input_path)
test_run = parameters.get('test_run', False)

rosetta_command = [
        workspace.rosetta_scripts_path,
        '-database', workspace.rosetta_database_path,
        '-in:file:s', input_path,
        '-in:file:native', workspace.input_pdb_path,
        '-out:prefix', output_subdir + '/',
        '-out:suffix', '_{0:03d}'.format(task_id / len(designs)),
        '-out:no_nstruct_label',
        '-out:overwrite',
        '-out:pdb_gz', 
        '-out:mute', 'protocols.loops.loops_main',
        '-parser:protocol', workspace.validate_script_path,
        '-parser:script_vars',
            'loop_file=' + workspace.loops_path,
            'fast=' + ('yes' if test_run else 'no'),
        '@', workspace.flags_path,
]
print ' '.join(rosetta_command)
subprocess.call(rosetta_command)
