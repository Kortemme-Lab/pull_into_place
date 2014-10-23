#!/usr/bin/env python2

"""\
Generate fragments for the design validation simulations.  Each design has a 
different sequence, so each input needs its own fragment library.  

Usage: 07_setup_design_fragments.py <name> <chain>
"""

import subprocess
from tools import docopt, scripting, bio, cluster
from tools.bio.pdb import PDB
from libraries import pipeline

with scripting.catch_and_print_errors():
    arguments = docopt.docopt(__doc__)
    cluster.require_chef()

    workspace = pipeline.RestrainedModels(arguments['<name>'])
    workspace.check_paths()
    workspace.make_dirs()
    workspace.clear_fragments()

    # Run the fragment generation script.

    workspace.cd('tools', 'bio', 'fragments')

    generate_fragments = [
            './generate_fragments.py',
            '--batch', workspace.input_dir,
            '--chain', arguments['<chain>'],
            '--outdir', workspace.fragments_dir,
    ]
    subprocess.call(generate_fragments)

