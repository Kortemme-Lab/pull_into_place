#!/usr/bin/env python2

"""\
Generate fragments for the design validation simulations.  Each design has a 
different sequence, so each input needs its own fragment library.  You can skip 
this step if you don't plan to use fragments in your validation simulations, 
but other algorithms may not perform as well on long loops.

Usage:
    pull_into_place 07_setup_design_fragments <workspace> <round> [options]

Options:
    -m, --mem-free=MEM  [default: 2]
        The amount of memory (GB) to request from the cluster.  Bigger systems 
        may need more memory, but making large memory requests can make jobs 
        take much longer to come off the queue (since there may only be a few 
        nodes with enough memory to meet the request).

    -d, --dry-run
        Print out the command-line that would be used to generate fragments, 
        but don't actually run it.
"""

import subprocess
from klab import docopt, scripting, bio, cluster
from .. import pipeline

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    cluster.require_qsub()

    workspace = pipeline.ValidatedDesigns(args['<workspace>'], args['<round>'])
    workspace.check_paths()
    workspace.check_rosetta()
    workspace.make_dirs()
    workspace.clear_fragments()

    # Run the fragment generation script.

    generate_fragments = [
            'klab_generate_fragments',
            '--loops_file', workspace.loops_path,
            '--outdir', workspace.fragments_dir,
            '--memfree', args['--mem-free'],
            workspace.input_dir,
    ]

    if args['--dry-run']:
        print ' '.join(generate_fragments)
    else:
        subprocess.call(generate_fragments)

