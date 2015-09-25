#!/usr/bin/env python2

"""\
Manually provide designs to validate.

The command accepts any number of pdb files, which should already contain the 
mutations you want to test.  These files are simply copied into the workspace 
in question.  The files are copied (not linked) so they're less fragile and 
easier to copy across the network.

Usage: 06_pick_manual_designs.py <name> <round> <pdbs>... [options]

Options:
    --clear, -x
        Forget about any designs that were previously picked for validation.
"""

import os, re, glob, shutil
from tools import docopt, scripting
from libraries import pipeline


with scripting.catch_and_print_errors():
    args = docopt.docopt(__doc__)
    name = args['<name>']
    round = args['<round>']
    pdbs = args['<pdbs>']

    # Setup the workspace.

    workspace = pipeline.ValidatedDesigns(name, round)
    workspace.check_paths()
    workspace.make_dirs()

    if args['--clear']:
        workspace.clear_inputs()

    # Copy the manual designs into the input directory.

    for source_path in pdbs:
        dest_path = os.path.join(workspace.input_dir, os.path.basename(source_path))
        shutil.copy(source_path, dest_path)
