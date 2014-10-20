#!/usr/bin/env python2

"""\
Query the user for all the input data needed for a design.  This includes a 
starting PDB file, the backbone regions that will be remodeled, the residues 
that will be allowed to design, and more.  A brief description of each field is 
given below.  This information is used to build a workspace for this design 
that will be used by the rest of the scripts in this pipeline.  

Usage: 01_setup_design.py <name> [--overwrite]

Options:
    --overwrite, -o
        If a design with the given name already exists, remove it and replace 
        it with the new design created by this script.
"""

import os, shutil

keys = (   # (fold)
        'rosetta_path',
        'input_pdb',
        'loops_path',
        'resfile_path',
        'restraints_path',
        'build_script',
        'design_script',
        'validate_script',
        'flags_path',
        'rsync_url',
)

prompts = {   # (fold)
        'rosetta_path': "Path to rosetta: ",
        'input_pdb': "Path to the input PDB file: ",
        'loops_path': "Path to the loops file: ",
        'resfile_path': "Path to resfile: ",
        'restraints_path': "Path to restraints file: ",
        'build_script': "Path to build script [optional]: ",
        'design_script': "Path to design script [optional]: ",
        'validate_script': "Path to validate script [optional]: ",
        'flags_path': "Path to flags file [optional]: ",
        'rsync_url': "Path to project on cluster [optional]: ",
}
descriptions = {   # (fold)
        'rosetta_path': """\
Rosetta checkout: Rosetta is used both locally and on the cluster.  Because 
paths are often different between machines, this setting is not copied to the 
cluster.  Instead, you must manually specify it by making a symlink called 
rosetta in the design directory.""",

        'input_pdb': """\
Input PDB file: A structure containing the functional groups to be positioned.  
This file should already be parse-able by rosetta, which often means it must be 
stripped of waters and miscellaneous ions.""",

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
default version of this script uses rama KIC in "ensemble-generation mode".""",

        'flags_path': """\
Flags file: A file containing command line flags that should be passed to every 
invocation of rosetta for this design.  For example, if your design involves a 
ligand, put flags related to the ligand parameter files in this file.""",

        'rsync_url': """\
Rsync path: An rsync path to your project files on a remote host.  This 
setting is used by scripts that keep the two locations in sync.""",

}

validators = {   # (fold)
        'rosetta_path': os.path.exists,
        'input_pdb': os.path.exists,
        'loops_path': os.path.exists,
        'resfile_path': os.path.exists,
        'restraints_path': os.path.exists,
        'build_script': os.path.exists,
        'design_script': os.path.exists,
        'validate_script': os.path.exists,
        'flags_path': os.path.exists,
}


from tools import docopt, scripting
from libraries import pipeline

with scripting.catch_and_print_errors():
    help = __doc__ + '\n' + '\n\n'.join(descriptions[x] for x in keys)
    arguments = docopt.docopt(help)
    workspace = pipeline.Workspace(arguments['<name>'])

    # Make sure this design doesn't already exist.

    if workspace.exists():
        if arguments['--overwrite']: shutil.rmtree(workspace.root_dir)
        else: scripting.print_error_and_die("Design '{0}' already exists.", workspace.root_dir)

    # Get the necessary paths from the user.

    print "Please provide the following pieces of information:"
    print

    settings = {}
    scripting.use_path_completion()

    for key in keys:
        print descriptions[key]
        print

        while True:
            settings[key] = raw_input(prompts[key])

            if settings[key] == '' and 'optional' in prompts[key]:
                print "Skipping optional input."
                break
            elif key not in validators or validators[key](settings[key]):
                break
            else:        
                print "'{0}' does not exist.".format(settings[key])
                print

        print

    # Fill in the design directory.

    workspace.make_dirs()

    rosetta_path = os.path.abspath(settings['rosetta_path'])
    os.symlink(rosetta_path, workspace.rosetta_dir)

    shutil.copyfile(settings['input_pdb'], workspace.input_pdb_path)
    shutil.copyfile(settings['loops_path'], workspace.loops_path)
    shutil.copyfile(settings['resfile_path'], workspace.resfile_path)
    shutil.copyfile(settings['restraints_path'], workspace.restraints_path)

    if settings['build_script']:
        shutil.copyfile(settings['build_script'], workspace.loopmodel_path)
    else:
        default_path = pipeline.big_job_path('build_models.xml')
        shutil.copyfile(default_path, workspace.loopmodel_path)

    if settings['design_script']:
        shutil.copyfile(settings['design_script'], workspace.fixbb_path)
    else:
        default_path = pipeline.big_job_path('design_models.xml')
        shutil.copyfile(default_path, workspace.fixbb_path)

    if settings['validate_script']:
        shutil.copyfile(settings['validate_script'], workspace.fixbb_path)
    else:
        default_path = pipeline.big_job_path('validate_designs.xml')
        shutil.copyfile(default_path, workspace.fixbb_path)

    if settings['flags_path']:
        shutil.copyfile(settings['flags_path'], workspace.flags_path)
    else:
        scripting.touch(workspace.flags_path)

    if settings['rsync_url']:
        with open(workspace.rsync_url_path, 'w') as file:
            file.write(settings['rsync_url'].strip() + '\n')

    print "Setup successful for design '{0}'.".format(workspace.root_dir)

