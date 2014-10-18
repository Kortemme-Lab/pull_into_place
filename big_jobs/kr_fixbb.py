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
        big_job.initiate(workspaces.AllFixbbDesigns)

bb_models = workspace.input_paths
bb_model = bb_models[task_id % len(bb_models)]

output_dir = workspace.output_dir
output_model = bb_model[:-len('.pdb.gz')]
output_num = task_id // len(bb_models)
output_prefix = '{0}/{1}_{2:03d}_'.format(output_dir, output_model, output_num)

rosetta_command = [
        workspace.rosetta_scripts_path,
        '-database', workspace.rosetta_database_path,
        '-in:file:s', bb_model,
        '-in:file:native', workspace.input_pdb_path,
        '-out:prefix', output_prefix,
        '-out:nstruct', '1',
        '-out:overwrite',
        '-out:pdb_gz', 
        '-parser:protocol', workspace.fixbb_path,
        '-packing:resfile', workspace.resfile_path,
        '-score:weights', 'talaris2013_cst',
        '-constraints:cst_fa_file', workspace.restraints_path,
        '@', workspace.flags_path,
]

subprocess.call(rosetta_command)
