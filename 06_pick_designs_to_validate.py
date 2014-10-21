#!/usr/bin/env python2

"""\
Pick a set of designs to validate.  This is actually a rather challenging task 
because so few designs can be validated.  Typically the decision is made based 
on sequence identity and rosetta score.  It might be nice to add a clustering 
component as well.

Usage: 06_pick_designs_to_validate.py <name> <round> [<queries>...] [options]

Options:
    --clear, -x
        Forget about any designs that were previously picked for validation.

    --recalc, -f
        Recalculate all the metrics that will be used to choose designs.

    --temp TEMP, -t TEMP        [default: 2.0]
        The parameter controlling how often low scoring designs are picked.

    --random-seed

    --num NUM, -n NUM           [default: 50]

    --dry-run

"""

import os, sys, pylab
from numpy import *
from tools import docopt, scripting
from libraries import pipeline, structures

with scripting.catch_and_print_errors():
    arguments = docopt.docopt(__doc__)
    name = arguments['<name>']
    round = arguments['<round>']
    query = ' and '.join(arguments['<queries>'])
    temp = float(arguments['--temp'])

    workspace = pipeline.ValidatedDesigns(name, round)
    workspace.check_paths()
    workspace.make_dirs()

    if arguments['--clear']:
        workspace.clear_inputs()

    predecessor = workspace.predecessor

    # Get sequences and scores for each design.

    seqs_scores = structures.load(
            predecessor.output_dir,
            predecessor.restraints_path,
            not arguments['--recalc'])
    print 'Total number of designs:      ', len(seqs_scores)

    # If a query was given on the command line, find models that satisfy it.

    if query:
        seqs_scores = seqs_scores.query(query)
        print '    minus given query:        ', len(seqs_scores)

    # Keep only the lowest scoring model for each set of identical sequences.

    groups = seqs_scores.groupby('sequence', group_keys=False)
    seqs_scores = groups.\
            apply(lambda df: df.ix[df.total_score.idxmin()]).\
            reset_index(drop=True)
    print '    minus duplicate sequences:', len(seqs_scores)
    
    # Remove designs that have already been picked.

    existing_inputs = set(os.path.basename(x) for x in workspace.input_paths)
    seqs_scores = seqs_scores.query('path not in @existing_inputs')
    print '    minus current inputs:     ', len(seqs_scores)
    print

    # Use a Boltzmann weighting scheme to pick designs.

    seqs_scores.sort('total_score', inplace=True)
    
    scores = seqs_scores.total_score.values
    scores -= max(scores)
    weights = exp(-scores / temp)
    indices = arange(len(scores))

    pdf = array(weights)
    cdf = cumsum(pdf) / sum(pdf)

    num_to_pick = min(int(arguments['--num']), len(scores))
    picked_indices = set()

    while len(picked_indices) < num_to_pick:
        choice = random.random()
        picked_index = indices[cdf > choice][0]
        picked_indices.add(picked_index)

    picked_indices = sorted(picked_indices)

    # Show the user the probability distributions used to pick designs.

    raw_input("""\
Press [enter] to view the designs that were picked and the distributions that
were used to pick them.  Pay particular attention to the CDF.  If it is too
flat, the temperature (T={0}) is too high and designs are essentially being
picked randomly.  If it is too sharp, the temperature is too low and only the 
highest scoring designs are being picked.
""".format(temp))

    base_format = dict()
    picked_format = dict(marker='o', ls='none', mfc='blue', mec='none')

    pylab.subplot(2, 2, 1)
    pylab.title('Rosetta Scores')
    pylab.plot(indices, scores, **base_format)
    pylab.plot(picked_indices, scores[picked_indices], **picked_format)

    pylab.subplot(2, 2, 2)
    pylab.title('Boltzmann Weights')
    pylab.plot(indices, weights, **base_format)
    pylab.plot(picked_indices, weights[picked_indices], **picked_format)
    pylab.yscale('log')

    pylab.subplot(2, 2, 3)
    pylab.title('Boltzmann PDF')
    pylab.plot(indices, pdf, **base_format)
    pylab.plot(picked_indices, pdf[picked_indices], **picked_format)
    pylab.yscale('log')

    pylab.subplot(2, 2, 4)
    pylab.title('Boltzmann CDF')
    pylab.plot(indices, cdf, **base_format)
    pylab.plot(picked_indices, cdf[picked_indices], **picked_format)

    pylab.show()

    if raw_input("Accept these picks? [Y/n] ") == 'n':
        print "Aborting."
        sys.exit()

    # Make symlinks to the picked designs.
    
    if not arguments['--dry-run']:
        for index in picked_indices:
            basename = seqs_scores.iloc[index]['path']
            target = os.path.join(predecessor.output_dir, basename)
            link_name = os.path.join(workspace.input_dir, basename)
            scripting.relative_symlink(target, link_name)

    print "Picked {} designs.".format(len(picked_indices))

    if arguments['--dry-run']:
        print "(Dry run: no symlinks created.)"
