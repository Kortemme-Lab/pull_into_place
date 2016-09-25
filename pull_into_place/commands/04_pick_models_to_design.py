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
    pull_into_place 04_pick_models_to_design [options]
        <workspace> <round> <queries>...

Options:
    --clear, -x
        Remove any previously selected "best" models.

    --recalc, -f
        Recalculate all the metrics that will be used to choose designs.

    --dry-run, -d
        Choose which models to pick, but don't actually make any symlinks.

Queries:
    The queries provided after the workspace name and round number are used to 
    decide which models to carry forward and which to discard.  Any number of 
    queries may be specified; only models that satisfy each query will be 
    picked.  The query strings use the same syntax of the query() method of 
    pandas DataFrame objects, which is pretty similar to python syntax.  
    Loosely speaking, each query must consist of a criterion name, a comparison 
    operator, and a comparison value.  Only 5 criterion names are recognized:

    "restraint_dist"
        The average distance between all the restrained atoms and their target 
        positions in a model. 
    "loop_dist"
        The backbone RMSD of a model relative to the input structure.
    "buried_unsat_score"
        The change in the number of buried unsatisfied H-bonds in a model 
        relative to the input structure.
    "dunbrack_score"
        The average Dunbrack score of any sidechains in a model that were 
        restrained during the loopmodel simulation.
    "total_score"
        The total score of a model.

    Some example query strings:

    'restraint_dist < 0.6'
    'buried_unsat_score <= 4'
"""

import os, glob
from klab import docopt, scripting
from .. import pipeline, structures

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    root, round = args['<workspace>'], args['<round>']
    query = ' and '.join(args['<queries>'])

    workspace = pipeline.FixbbDesigns(root, round)
    workspace.check_paths()
    workspace.make_dirs()

    if args['--clear']:
        workspace.clear_inputs()

    predecessor = workspace.predecessor
    num_models, num_selected, num_duplicates = 0, 0, 0
    
    for input_subdir in predecessor.output_subdirs:
        # Find models meeting the criteria specified on the command line.

        all_score_dists = structures.load(
                input_subdir,
                use_cache=not args['--recalc'],
        )
        best_score_dists = all_score_dists.query(query)
        best_inputs = set(best_score_dists['path'])

        num_models += len(all_score_dists)
        num_selected += len(best_inputs)

        # Figure out which models have already been considered.

        existing_ids = set(
                int(os.path.basename(x)[0:-len('.pdb.gz')])
                for x in glob.glob(os.path.join(
                    workspace.input_dir, '*.pdb.gz')))

        next_id = max(existing_ids) + 1 if existing_ids else 0

        existing_inputs = set(
                os.path.basename(os.readlink(x))
                for x in workspace.input_paths)

        new_inputs = best_inputs - existing_inputs
        num_duplicates += len(best_inputs & existing_inputs)

        # Make symlinks to the new models.

        if not args['--dry-run']:
            for id, new_input in enumerate(new_inputs, next_id):
                target = os.path.join(input_subdir, new_input)
                link_name = os.path.join(workspace.input_dir, '{0:05d}.pdb.gz')
                scripting.relative_symlink(target, link_name.format(id))

    # Tell the user what happened.

    plural = lambda x: 's' if x != 1 else ''

    print "Selected {} of {} model{}.".format(
            num_selected, num_models, plural(num_selected))

    if num_duplicates:
        print "Skipping {} duplicate model{}.".format(
                num_duplicates, plural(num_duplicates))

    if args['--dry-run']:
        print "(Dry run: no symlinks created.)"

