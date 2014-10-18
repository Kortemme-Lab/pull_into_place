#!/usr/bin/env python2

"""\
Pick backbone models from the restrained loopmodel simulations to carry on 
though the rest of the design pipeline.  The next step in the pipeline is to 
search for the sequences that best stabilize these models.  Models can be 
picked based on number of criteria, including how well the model satisfies the 
given restraints and how many buried unsatisfied H-bonds are present in the 
model.  All of the criteria that can be used are described in the "Queries" 
section below.

Usage: 04_pick_restrained_models.py [options] <name> <queries>...

Options:
    --clear
        Remove any previously selected "best" models.

Queries:
    The queries provided after the design name are used to decide which models 
    to carry forward and which to discard.  Any number of queries may be 
    specified; only models that satisfy each query will be picked.  The query 
    strings use the same syntax of the query() method of pandas DataFrame 
    objects, which is pretty similar to python syntax.  Loosely speaking, each 
    query must consist of a criterion name, a comparison operator, and a 
    comparison value.  Only 5 criterion names are recognized:

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

if __name__ == '__main__':
    import os
    from tools import docopt, scripting
    from libraries import workspaces, metrics

    with scripting.catch_and_print_errors():
        arguments = docopt.docopt(__doc__)

        # Setup the workspace.

        workspace = workspaces.BestRestrainedModels(arguments['<name>'])
        workspace.make_dirs()
        workspace.check_paths()

        if arguments['--clear']:
            workspace.clear_outputs()

        # Find models meeting the criteria specified on the command line.

        query = ' and '.join(arguments['<queries>'])
        all_score_dists = metrics.load(workspace.input_dir)
        best_score_dists = all_score_dists.query(query)
        best_sources = set(best_score_dists['path'])

        # Figure out which models have already been considered.

        existing_ids = set(
                int(x[0:-len('.pdb.gz')])
                for x in os.listdir(workspace.output_dir))

        next_id = max(existing_ids) + 1 if existing_ids else 0

        existing_sources = set(
                os.path.basename(os.readlink(x))
                for x in workspace.output_paths)

        new_sources = best_sources - existing_sources
        duplicate_sources = best_sources & existing_sources

        # Make symlinks to the new models.

        for id, path in enumerate(new_sources, next_id):
            source_path = os.path.join(workspace.symlink_prefix, path)
            dest_path = os.path.join(workspace.output_dir, '{0:05d}.pdb.gz'.format(id))
            os.symlink(source_path, dest_path)

        # Tell the user what happened.

        plural = lambda x: 's' if len(x) != 1 else ''

        print "Selected {} of {} model{}.".format(
                len(best_sources), len(all_score_dists), plural(best_sources))

        if duplicate_sources:
            print "Skipping {} duplicate model{}.".format(
                    len(duplicate_sources), plural(duplicate_sources))
