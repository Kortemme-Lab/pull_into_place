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

workspace, job_id, task_id, parameters = big_job.initiate()

bb_models = parameters['inputs']
bb_model = bb_models[task_id % len(bb_models)]
nstruct = parameters['designs_per']

rosetta_command = [
        workspace.rosetta_scripts_path,
        '-database', workspace.rosetta_database_path,
        '-in:file:s', bb_model,
        '-in:file:native', workspace.input_pdb_path,
        '-out:prefix', workspace.output_dir + '/',
        '-out:nstruct', str(nstruct),
        '-out:overwrite',
        '-out:pdb_gz', 
        '-parser:protocol', workspace.design_script_path,
        '-parser:script_vars', 'cst_file=' + workspace.restraints_path,
        '-packing:resfile', workspace.resfile_path,
        '@', workspace.flags_path,
]

subprocess.call(rosetta_command)
