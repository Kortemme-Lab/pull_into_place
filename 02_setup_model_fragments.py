#!/usr/bin/env python2

"""\
Generate fragments for the initial model building simulations.  Note that it's 
a little bit weird to use fragments even though the models are allowed to 
design in these simulations.  Conformations that are common for the current 
sequence but rare for the original one might not get sampled.  However, we 
believe that the improved sampling that fragments offer outweighs this 
potential drawback.

Usage:
    02_setup_model_fragments.py <name> [options]

Options:
    -m, --mem-free=MEM  [default: 2GB]
        The amount of memory to request from the cluster.  Bigger systems may 
        need more memory, But making large memory requests can make jobs take 
        much longer to come off the queue (since there may only be a few nodes 
        with enough memory to meet the request).

    -d, --dry-run
        Print out the command-line that would be used to generate fragments, 
        but don't actually run it.
        
"""

import subprocess
from tools import docopt, scripting, cluster
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
            '--loops_file', workspace.loops_path,
            '--outdir', workspace.fragments_dir,
            '--memfree', args['--mem-free'],
            workspace.input_pdb_path,
    ]

    if args['--dry-run']:
        print ' '.join(generate_fragments)
    else:
        subprocess.call(generate_fragments)
