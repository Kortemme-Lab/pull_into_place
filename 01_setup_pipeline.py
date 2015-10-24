#!/usr/bin/env python2

"""\
Query the user for all the input data needed for a design.  This includes a 
starting PDB file, the backbone regions that will be remodeled, the residues 
that will be allowed to design, and more.  A brief description of each field is 
given below.  This information is used to build a workspace for this design 
that will be used by the rest of the scripts in this pipeline.  

Usage:
    01_setup_pipeline.py <name> [--remote] [--overwrite]

Options:
    --remote, -r
        Setup a link to a design directory on a remote machine, to help with 
        transferring data between a workstation and a cluster.  Note: the 
        remote and local design directories must have the same name.

    --overwrite, -o
        If a design with the given name already exists, remove it and replace 
        it with the new design created by this script.
"""

import os, re, shutil, subprocess

def ensure_path_exists(path):
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        print "'{0}' does not exist.".format(path)
        raise ValueError
    return path

def install_rosetta_dir(workspace, rosetta_dir):
    rosetta_dir = ensure_path_exists(rosetta_dir)
    rosetta_subdirs = [
            os.path.join(rosetta_dir, 'database'),
            os.path.join(rosetta_dir, 'tests'),
            os.path.join(rosetta_dir, 'source'),
            os.path.join(rosetta_dir, 'source', 'bin'),
    ]
    rosetta_subdirs_exist = map(os.path.exists, rosetta_subdirs)

    if not all(rosetta_subdirs_exist):
        print "'{0}' does not appear to be the main rosetta directory.".format(rosetta_dir)
        print "The following subdirectories are missing:"
        for path in rosetta_subdirs:
            if not os.path.exists(path):
                print "    " + path
        raise ValueError

    os.symlink(rosetta_dir, workspace.rosetta_dir)

def install_input_pdb(workspace, pdb_path):
    pdb_path = ensure_path_exists(pdb_path)
    if pdb_path.endswith('.pdb.gz'):
        shutil.copyfile(pdb_path, workspace.input_pdb_path)
    elif pdb_path.endswith('.pdb'):
        subprocess.call('gzip -c {} > {}'.format(
                pdb_path, workspace.input_pdb_path), shell=True)
    else:
        print "'{0}' is not a PDB file.".format(pdb_path)
        raise ValueError

def install_loops_file(workspace, loops_path):
    loops_path = ensure_path_exists(loops_path)
    shutil.copyfile(loops_path, workspace.loops_path)

def install_resfile(workspace, resfile_path):
    resfile_path = ensure_path_exists(resfile_path)
    shutil.copyfile(resfile_path, workspace.resfile_path)

def install_restraints_file(workspace, restraints_path):
    restraints_path = ensure_path_exists(restraints_path)
    shutil.copyfile(restraints_path, workspace.restraints_path)

def install_build_script(workspace, script_path):
    if script_path:
        script_path = ensure_path_exists(script_path)
        shutil.copyfile(script_path, workspace.build_script_path)
    else:
        default_path = pipeline.big_job_path('build_models.xml')
        shutil.copyfile(default_path, workspace.build_script_path)

def install_design_script(workspace, script_path):
    if script_path:
        script_path = ensure_path_exists(script_path)
        shutil.copyfile(script_path, workspace.design_script_path)
    else:
        default_path = pipeline.big_job_path('design_models.xml')
        shutil.copyfile(default_path, workspace.design_script_path)

def install_validate_script(workspace, script_path):
    if script_path:
        script_path = ensure_path_exists(script_path)
        shutil.copyfile(script_path, workspace.validate_script_path)
    else:
        default_path = pipeline.big_job_path('validate_designs.xml')
        shutil.copyfile(default_path, workspace.validate_script_path)

def install_flags_file(workspace, flags_path):
    if flags_path:
        flags_path = ensure_path_exists(flags_path)
        shutil.copyfile(flags_path, workspace.flags_path)
    else:
        scripting.touch(workspace.flags_path)

def install_rsync_url(workspace, rsync_url):
    with open(workspace.rsync_url_path, 'w') as file:
        file.write(rsync_url.strip() + '\n')


local_keys = (   # (fold)
        'rosetta_dir',
        'input_pdb',
        'loops_path',
        'resfile_path',
        'restraints_path',
        'build_script',
        'design_script',
        'validate_script',
        'flags_path',
)

remote_keys = (  # (fold)
        'rosetta_dir',
        'rsync_url',
)

prompts = {   # (fold)
        'rosetta_dir': "Path to rosetta: ",
        'input_pdb': "Path to the input PDB file: ",
        'loops_path': "Path to the loops file: ",
        'resfile_path': "Path to resfile: ",
        'restraints_path': "Path to restraints file: ",
        'build_script': "Path to build script [optional]: ",
        'design_script': "Path to design script [optional]: ",
        'validate_script': "Path to validate script [optional]: ",
        'flags_path': "Path to flags file [optional]: ",
        'rsync_url': "Path to project on remote host: ",
}
descriptions = {   # (fold)
        'rosetta_dir': """\
Rosetta checkout: Path to the main directory of a Rosetta source code checkout.  
This is the directory called 'main' in a normal rosetta checkout.  Rosetta is 
used both locally and on the cluster, but the path you specify here probably 
won't apply to both machines.  You can manually correct the path by changing 
the symlink called 'rosetta' in the workspace directory.""",

        'input_pdb': """\
Input PDB file: A structure containing the functional groups to be positioned.  
This file should already be parse-able by rosetta, which often means it must be 
stripped of waters and extraneous ligands.""",

        'loops_path': """\
Loops file: A file specifying which backbone regions will be allowed to move.  
These backbone regions do not have to be contiguous, but each region must span 
at least 4 residues.""",

        'resfile_path': """\
Resfile: A file specifying which positions to design and which positions to 
repack.  I recommend designing as few residues as possible outside the loops.""",

        'restraints_path': """\
Restraints file: A file describing the geometry you're trying to design.  In 
rosetta parlance, this is more often (inaccurately) called a constraint file.  
Note that restraints are only used to build the initial set of models.""",

        'build_script': """\
Build script: An XML rosetta script that generates backbones capable of 
supporting the desired geometry.  The default version of this script uses KIC 
with fragments in "ensemble-generation mode" (i.e. no initial build step).""",

        'design_script': """\
Design script: An XML rosetta script that performs design (usually on a fixed 
backbone) to stabilize the desired geometry.  The default version of this 
script uses fixbb.""",

        'validate_script': """\
Validate script: An XML rosetta script that samples the designed loop to 
determine whether the desired geometry is really the global score minimum.  The 
default version of this script uses KIC with fragments in "ensemble-generation 
mode" (i.e. no initial build step).""",

        'flags_path': """\
Flags file: A file containing command line flags that should be passed to every 
invocation of rosetta for this design.  For example, if your design involves a 
ligand, put flags related to the ligand parameter files in this file.""",

        'rsync_url': """\
Rsync URL: An ssh-style path to the directory that contains (i.e. is one level 
above) the remote workspace.  This workspace must have the same name as the 
remote one.  For example, to link to "/path/to/my_design" on chef, name this 
workspace "my_design" and set its rsync URL to "chef:path/to".""",

}

installers = {   # (fold)
        'rosetta_dir': install_rosetta_dir,
        'input_pdb': install_input_pdb,
        'loops_path': install_loops_file,
        'resfile_path': install_resfile,
        'restraints_path': install_restraints_file,
        'build_script': install_build_script,
        'design_script': install_design_script,
        'validate_script': install_validate_script,
        'flags_path': install_flags_file,
        'rsync_url': install_rsync_url,
}


from tools import docopt, scripting
from libraries import pipeline

with scripting.catch_and_print_errors():
    arguments = docopt.docopt(__doc__)
    workspace = pipeline.Workspace(arguments['<name>'])

    # Make a new workspace.

    if workspace.exists():
        if arguments['--overwrite']: shutil.rmtree(workspace.root_dir)
        else: scripting.print_error_and_die("Design '{0}' already exists.", workspace.root_dir)

    workspace.make_dirs()

    # Decide which settings to ask for.

    if arguments['--remote']:
        keys = remote_keys
    else:
        keys = local_keys

    # Get the necessary settings from the user and use them to fill in the 
    # workspace.

    print "Please provide the following pieces of information:"
    print

    settings = {}
    scripting.use_path_completion()

    for key in keys:
        print descriptions[key]
        print

        while True:
            try:
                settings[key] = raw_input(prompts[key])
                installers[key](workspace, settings[key])
            except ValueError:
                continue
            else:
                break

        print

    # If we made a link to a remote workspace, immediately try to synchronize 
    # with it.  Rsync will say whether or not it succeeded.  Otherwise just 
    # print a success message.

    if arguments['--remote']:
        pipeline.fetch_data(workspace.root_dir)
    else:
        print "Setup successful for design '{0}'.".format(workspace.root_dir)
