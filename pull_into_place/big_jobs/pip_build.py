#!/usr/bin/env python2

#$ -S /usr/bin/python
#$ -l mem_free=1G
#$ -l arch=linux-x64
#$ -l netapp=1G
#$ -cwd

import os, sys, subprocess
from pull_into_place import big_jobs

workspace, job_id, task_id, parameters, validate_directory = big_jobs.initiate()
output_prefix = '{0}/{1}_{2:06d}_'.format(workspace.output_dir, job_id, task_id)
test_run = parameters.get('test_run', False)

design_number = '{0:03d}'.format(task_id)
if len(workspace.loops_path) > 1:
    fragments_dir = '../' + workspace_validate_path + '/fragments/' + design_number + 'A/'
else:
    fragments_dir = '../' + workspace_validate_path + '/fragments/' + design_number

big_jobs.print_debug_info()
big_jobs.run_command([
        workspace.rosetta_scripts_path,
        '-database', workspace.rosetta_database_path,
        '-in:file:s', workspace.input_pdb_path,
        '-in:file:native', workspace.input_pdb_path,
        '-in:file:vall', workspace.rosetta_database_path + 'sampling/vall.jul19.2011.gz',
        '-frags:scoring:config', workspace.root_dir + '/standard_fragment.wts',
        '-in:file:checkpoint', fragments_dir + '{0:04d}A.checkpoint'.format(task_id),
        '-spine_x', fragments_dir + design_number + 'A.fasta.phipsi',
        '-frags:ss_pred', fragments_dir + design_number + 'A.psipred_ss2', 'predA',
        '-out:prefix', output_prefix,
        '-out:no_nstruct_label',
        '-out:overwrite',
        '-out:pdb_gz',
        '-out:mute', 'protocols.loops.loops_main',
        '-parser:protocol', workspace.build_script_path,
        '-parser:script_vars',
            'wts_file=' + workspace.scorefxn_path,
            'cst_file=' + workspace.restraints_path,
            'loop_file=' + workspace.loops_path,
            'fast=' + ('yes' if test_run else 'no'),
            'loop_start=' + str(workspace.loop_boundaries[0]),
            'loop_end=' + str(workspace.loop_boundaries[1]),
        '-packing:resfile', workspace.resfile_path,
        '-constraints:cst_fa_file', workspace.restraints_path,
] +     workspace.fragments_flags(workspace.input_pdb_path) + [
        '@', workspace.flags_path,
])
