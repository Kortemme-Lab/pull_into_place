#!/usr/bin/env python2

"""\
Generate fragments for the initial model building simulations.  Note that it's 
a little bit weird to use fragments even though the models are allowed to 
design in these simulations.  Conformations that are common for the current 
sequence but rare for the original one might not get sampled.  However, we 
believe that the improved sampling that fragments offer outweighs this 
potential drawback.

Usage: 02_setup_model_fragments.py <name> <chain>
"""

import subprocess
from tools import docopt, scripting, bio, cluster
from tools.bio.pdb import PDB
from libraries import pipeline

with scripting.catch_and_print_errors():
    args = docopt.docopt(__doc__)
    cluster.require_qsub()

    workspace = pipeline.RestrainedModels(args['<name>'])
    workspace.check_paths()
    workspace.make_dirs()
    workspace.clear_fragments()

    # Run the fragment generation script.

    generate_fragments = [
            'tools/bio/fragments/generate_fragments.py',
            '--chain', args['<chain>'],
            '--loop_file', workspace.loops_path,
            '--outdir', workspace.fragments_dir,
            workspace.input_pdb_path,
    ]
    subprocess.call(generate_fragments)
