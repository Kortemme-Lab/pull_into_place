#!/usr/bin/env python2

"""\
Pick backbone models from the restrained loopmodel simulations to carry on
though the rest of the design pipeline.  The next step in the pipeline is to
search for the sequences that best stabilize these models.  Models can be
picked based on number of criteria, including how well the model satisfies the
given restraints and how many buried unsatisfied H-bonds are present in the
model.  All of the criteria that can be used are described in the "Queries"
section below.

Usage:
    pull_into_place 04_pick_models_to_design
        <workspace> <round> [<picks>] [options]

Options:
    --clear, -x
        Remove any previously selected "best" models.

    --recalc, -f
        Recalculate all the metrics that will be used to choose designs.

    --dry-run, -d
        Choose which models to pick, but don't actually make any symlinks.
"""

import os, glob
from klab import docopt, scripting
from pandas.core.computation.ops import UndefinedVariableError
from .. import pipeline, structures

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    root, round = args['<workspace>'], args['<round>']

    workspace = pipeline.FixbbDesigns(root, round)
    workspace.check_paths()
    workspace.make_dirs()

    structures.make_picks(
            workspace, 
            args['<picks>'],
            clear=args['--clear'],
            use_cache=not args['--recalc'],
            dry_run=args['--dry-run'],
            keep_dups=True,
    )
    

