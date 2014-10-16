#!/usr/bin/env python2

#$ -S /usr/bin/python
#$ -l mem_free=1G
#$ -l arch=linux-x64
#$ -l netapp=1G
#$ -l h_core=0
#$ -cwd

import os, sys; sys.path.append(os.getcwd())
import subprocess
from libraries import big_job
from libraries import workspaces

workspace, job_id, task_id, parameters = \
        big_job.initiate(workspaces.AllRestrainedModels)

output_prefix = '{0}/{1}_{2:06d}_'.format(workspace.output_dir, job_id, task_id)
test_run = parameters.get('test_run', False)

rosetta_command = [
        workspace.rosetta_scripts_path,
        '-database', workspace.rosetta_database_path,
        '-in:file:s', workspace.input_pdb_path,
        '-in:file:native', workspace.input_pdb_path,
        '-out:prefix', output_prefix,
        '-out:nstruct', '1',
        '-out:overwrite',
        '-out:pdb_gz', 
        '-parser:protocol', 'workhorses/loopmodel.xml',
        '-parser:script_vars',
            'loop_file=' + workspace.loops_path,
            'fast=' + ('yes' if test_run else 'no'),
        '-packing:resfile', workspace.resfile_path,
        '-constraints:cst_fa_weight', '1.0',
        '-constraints:cst_fa_file', workspace.restraints_path,
        '-loops:frag_sizes'] + workspace.fragments_sizes + [
        '-loops:frag_files'] + workspace.fragments_paths + [
        '@', workspace.flags_path,
]

subprocess.call(rosetta_command)
