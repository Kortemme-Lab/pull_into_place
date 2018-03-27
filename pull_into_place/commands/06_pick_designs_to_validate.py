#!/usr/bin/env python2

"""\
Pick the designs that are at or near the Pareto front of the given metrics to 
validate in the next step.

Usage:
    pull_into_place 06_pick_designs_to_validate
            <workspace> <round> <metrics>... [options]

Options:
    --depth LEVEL, -n LEVEL         [default: 1]
        The number of Pareto fronts to return.  In other words, if --depth=2, 
        the Pareto front of all the design will be calculated, then those 
        designs (and any within epsilon of them) will be set aside, then the 
        Pareto front of the remaining designs will be calculated, then the 
        union of both fronts will be selected.
        
    --epsilon PERCENT, -e PERCENT
        How similar two designs can be in all the metrics considered before 
        they are considered the same and one is excluded from the Pareto front 
        (even if it is non-dominated).  This is roughly in units of percent of 
        the range of the points.

    --clear, -x
        Forget about any designs that were previously picked for validation.

    --recalc, -f
        Recalculate all the metrics that will be used to choose designs.

    --dry-run, -d
        Don't actually fill in the input directory of the validation workspace.  
        Instead just report how many designs would be picked.

Metrics:
    The given metrics specify which scores will be used to construct the Pareto 
    front.  You can refer to any of the metrics available in the 'plot_funnels' 
    GUI by making the title lowercase, replacing any spaces or dashes with 
    underscores, and removing any special characters.

    In order for this to work, PIP needs to understand whether high values or 
    low values are favorable for each individual metric.  This is taken care of 
    for all the built-in metrics, but if you've added any filters to the 
    pipeline, you need to specify this by adding a short code to your filters' 
    names: "[+]" if bigger is better, or "[-]" if smaller is better.

    You can also specify thresholds for each metric being considered.  This is 
    done using the same syntax of the query() method of pandas DataFrame 
    objects, which is pretty similar to python syntax.  Loosely speaking, each 
    query must consist of a criterion name, a comparison operator, and a 
    comparison value.  There is an example of this syntax below.

Tuning:
    Depending on the round, you often want to validate between 50-500 designs.  
    However, there's no direct way to control exactly how many designs get 
    selected.  Instead, you have to use the --depth and --epsilon options to 
    tune both the quantity and diversity of designs that are selected.

    Increasing --depth increases the number of designs that are selected, 
    because it includes designs that are the given number of steps back from 
    the Pareto front.

    Increasing --epsilon decreases the number of designs that are selected, but 
    increases the diversity of those designs, because it excludes designs that 
    have very similar scores across all the metrics being considered.
    
Examples:
    A basic selection:
    $ pull_into_place 06_pick /path/to/project 1 \\
            total_score restraint_dist

    Assuming we've added a filter called "Hydrophobic SASA [-]":
    $ pull_into_place 06_pick /path/to/project 1 \\
            total_score restraint_dist hydrophobic_sasa

    Threshold the restraint distance:
    $ pull_into_place 06_pick /path/to/project 1 \\
            total_score 'restraint_dist < 1.0'

    Increase the number of models to select:
    $ pull_into_place 06_pick /path/to/project 1 \\
            total_score restraint_dist -d5

    Decrease the number of models to select:
    $ pull_into_place 06_pick /path/to/project 1 \\
            total_score restraint_dist -e5
"""

import os, sys, re
import pandas as pd
from numpy import *
from klab import docopt, scripting
from .. import pipeline, structures
from pprint import pprint

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    root = args['<workspace>']
    round = args['<round>']

    workspace = pipeline.ValidatedDesigns(root, round)
    workspace.check_paths()
    workspace.make_dirs()

    if args['--clear']:
        workspace.clear_inputs()

    predecessor = workspace.predecessor
    seqs_scores, score_metadata = structures.load(
            predecessor.output_dir,
            use_cache=not args['--recalc'],
    )
    metrics, queries = parse_metrics(args['<metrics>'], score_metadata)

    # Get sequences and scores for each design.

    seqs_scores.dropna(inplace=True)
    print 'Total number of designs:      ', len(seqs_scores)

    # If a query was given on the command line, find models that satisfy it.

    if queries:
        seqs_scores = seqs_scores.query(' and '.join(queries))
        print '    minus given query:        ', len(seqs_scores)

    # Keep only the lowest scoring model for each set of identical sequences.

    groups = seqs_scores.groupby('sequence', group_keys=False)
    seqs_scores = groups.\
            apply(lambda df: df.ix[df.total_score.idxmin()]).\
            reset_index(drop=True)
    print '    minus duplicate sequences:', len(seqs_scores)
    
    # Remove designs that aren't in the Pareto front.

    def progress(i, depth, j, front): #
        sys.stderr.write('\x1b[2K\r    minus Pareto dominated:    calculating... [{}/{}] [{}/{}]'.format(i, depth, j, front))
        if i == depth and j == front:
            sys.stderr.write('\x1b[2K\r')
        sys.stderr.flush()

    seqs_scores = structures.find_pareto_front(
            seqs_scores, score_metadata, metrics,
            depth=int(args['--depth']),
            epsilon=args['--epsilon'] and float(args['--epsilon']),
            progress=progress,
    )
    print '    minus Pareto dominated:   ', len(seqs_scores)

    # Remove designs that have already been picked.

    existing_inputs = set(
            os.path.basename(os.path.realpath(x))
            for x in workspace.input_paths)
    seqs_scores = seqs_scores.query('path not in @existing_inputs')
    print '    minus current inputs:     ', len(seqs_scores)
    print

    if not args['--dry-run']:
        existing_ids = set(
                int(x[0:-len('.pdb.gz')])
                for x in os.listdir(workspace.input_dir)
                if x.endswith('.pdb.gz'))
        next_id = max(existing_ids) + 1 if existing_ids else 0

        for id, picked_index in enumerate(seqs_scores.index, next_id):
            basename = seqs_scores.loc[picked_index]['path']
            target = os.path.join(predecessor.output_dir, basename)
            link_name = os.path.join(workspace.input_dir, '{0:04}.pdb.gz')
            scripting.relative_symlink(target, link_name.format(id))

    print "Picked {} designs.".format(len(seqs_scores))

    if args['--dry-run']:
        print "(Dry run: no symlinks created.)"

def parse_metrics(args, metadata):
    metrics = set()
    queries = []

    for arg in args:
        expr = re.match('(\w+)\s*[=!<> ].*', arg)
        if expr:
            metrics.add(expr.group(1))
            queries.append(arg)
        else:
            metrics.add(arg)

    unknown_metrics = metrics - set(metadata)
    if unknown_metrics:
        message = """\
The following metrics are not understood:
{0}

Did you mean:
{1}""" + '\n\n'
        not_understood = '\n'.join('    ' + x for x in sorted(unknown_metrics))
        did_you_mean = '\n'.join('    ' + x for x in sorted(metadata))
        scripting.print_error_and_die(
                message.format(not_understood, did_you_mean))

    return metrics, queries


