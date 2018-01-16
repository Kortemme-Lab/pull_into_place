#!/usr/bin/env python2

"""\
Count the number of models meeting the given query.

Usage:
    pull_into_place count_models <directories>... [options]

Options:
    --query QUERY, -q QUERY
        Specify which models to include in the count.

    --recalc, -f
        Recalculate all the metrics that will be used to choose designs.

    --restraints PATH
        The path to a set of restraints that can be used to recalculate the 
        restraint_distance metric.  This is only necessary if the cache is 
        being regenerated in a directory that is not a workspace.

Queries:
    The query strings use the same syntax of the query() method of pandas 
    DataFrame objects, which is pretty similar to python syntax.  Loosely 
    speaking, each query must consist of a criterion name, a comparison 
    operator, and a comparison value.  Five criterion names are recognized by 
    default:

    "restraint_dist"
        The average distance between all the restrained atoms and their target 
        positions in a model.
    "loop_rmsd"
        The backbone RMSD of a model relative to the input structure.
    "buried_unsat_score"
        The change in the number of buried unsatisfied H-bonds in a model 
        relative to the input structure.
    "dunbrack_score"
        The average Dunbrack score of any sidechains in a model that were 
        restrained during the loopmodel simulation.
    "total_score"
        The total score of a model.

    You can also include in your query any of the filters that were used to 
    score the models in question.  To do this, use the filter's title in 
    lowercase with underscores instead of spaces and any bracketed expressions 
    or non-alphanumeric characters removed.  For example, for a filter named 
    "PackStat Score [[+]]", a query would look like "packstat_score > 0.67".

    Some example query strings:

    'restraint_dist < 0.6'
    'buried_unsat_score <= 4'
"""

import os
from klab import docopt, scripting
from .. import pipeline, structures

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    num_models = 0

    for directory in args['<directories>']:
        records = structures.\
                load(directory, args['--restraints'], not args['--recalc'])
        if args['--query']:
            records = records.query(args['--query'])
        num_models += len(records)

    print num_models

