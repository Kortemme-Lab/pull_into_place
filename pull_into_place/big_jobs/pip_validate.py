#!/usr/bin/env python2

#$ -S /usr/bin/python
#$ -l mem_free=1G
#$ -l arch=linux-x64
#$ -l netapp=1G
#$ -cwd

import os, sys, subprocess
from pull_into_place import big_jobs

workspace, job_id, task_id, parameters = big_jobs.initiate()

designs = parameters['inputs']
design = designs[task_id % len(designs)]
test_run = parameters.get('test_run', False)

big_jobs.print_debug_info()
big_jobs.run_command([
        workspace.rosetta_scripts_path,
        '-database', workspace.rosetta_database_path,
        '-in:file:s', workspace.input_path(design),
        '-in:file:native', workspace.input_pdb_path,
        '-out:prefix', workspace.output_subdir(design) + '/',
        '-out:suffix', '_{0:03d}'.format(task_id / len(designs)),
        '-out:no_nstruct_label',
        '-out:overwrite',
        '-out:pdb_gz', 
        '-out:mute', 'protocols.loops.loops_main',
        '-parser:protocol', workspace.validate_script_path,
        '-parser:script_vars',
            'wts_file=' + workspace.scorefxn_path,
            'loop_file=' + workspace.loops_path,
            'fast=' + ('yes' if test_run else 'no')
] +     workspace.fragments_flags(design) + [
        '@', workspace.flags_path,
])
