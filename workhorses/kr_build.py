#!/usr/bin/env python2

#$ -S /usr/bin/python
#$ -l mem_free=1G
#$ -l arch=linux-x64
#$ -l netapp=1G
#$ -l h_core=0
#$ -cwd

from libraries import cluster
from libraries import workspaces

name, task_id, test_run = cluster.parse_args()
workspace = workspaces.AllRestrainedModels(name)

rosetta_command = [
        workspace.rosetta_scripts_path,
        '-database', workspace.rosetta_database_path,
        '-in:file:s', workspace.input_pdb_path,
        '-in:file:native', workspace.input_pdb_path,
        '-out:prefix', workspace.subdir_path + '/',
        '-out:nstruct', '1',
        '-out:overwrite',
        '-out:pdb_gz', 
        '-parser:protocol', 'workhorses/loopmodel.xml',
        '-parser:script_vars',
            'loop_file=' + workspace.loop_path,
            'fast=' + ('yes' if test_run else 'no'),
        '-packing:resfile', workspace.resfile_path,
        '-constraints:cst_fa_file', workspace.restraints_file,
        '-loops:frag_sizes'] + workspace.fragment_sizes + [
        '-loops:frag_files'] + workspace.fragment_paths + [
        '@', workspace.flags_file,
]

subprocess.call(rosetta_command)
