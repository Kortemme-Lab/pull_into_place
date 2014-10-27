#!/usr/bin/env python2

"""\
Generate fragments for the design validation simulations.  Each design has a 
different sequence, so each input needs its own fragment library.  You can skip 
this step if you don't plan to use fragments in your validation simulations, 
but other algorithms may not perform as well on long loops.

Usage: 07_setup_design_fragments.py <name> <round> <chain>
"""

import subprocess
from tools import docopt, scripting, bio, cluster
from tools.bio.pdb import PDB
from libraries import pipeline

with scripting.catch_and_print_errors():
    args = docopt.docopt(__doc__)
    cluster.require_chef()

    workspace = pipeline.ValidatedDesigns(args['<name>'], args['<round>'])
    workspace.check_paths()
    workspace.make_dirs()
    workspace.clear_fragments()

    # Run the fragment generation script.

    generate_fragments = [
            'tools/bio/fragments/generate_fragments.py',
            '--chain', args['<chain>'],
            '--loops_file', workspace.loops_path,
            '--outdir', workspace.fragments_dir,
            workspace.input_dir,
    ]
    subprocess.call(generate_fragments)

