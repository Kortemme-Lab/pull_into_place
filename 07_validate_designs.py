#!/usr/bin/env python2

"""\
ugh...
Usage: 07_validate_designs.py <name> <round> [options]

Options:
    --nstruct NUM, -n NUM   [default: 500]
        The number of simulations to run per design.
        
    --max-runtime TIME      [default: 12:00:00]
        The runtime limit for each model building job.

    --max-memory MEM        [default: 1G]
        The memory limit for each model building job.

    --test-run
        Run on the short queue with a limited number of iterations.  This 
        option automatically clears old results.

    --clear
        Clear existing results before submitting new jobs.
"""

from libraries import pipeline, big_job
from tools import docopt, scripting, cluster

with scripting.catch_and_print_errors():
    args = docopt.docopt(__doc__)
    cluster.require_chef()

    # Setup the workspace.

    workspace = pipeline.ValidatedDesigns(args['<name>'], args['<round>'])
    workspace.check_paths()
    workspace.make_dirs()

    if args['--clear'] or args['--test-run']:
        workspace.clear_outputs()

    # Setup an output directory for each input.

    inputs = workspace.unclaimed_inputs
    nstruct = len(inputs) * int(args['--nstruct'])

    for input in inputs:
        subdir = workspace.output_subdir(input)
        scripting.clear_directory(subdir)

    # Launch the validation job.

    big_job.submit(
            'kr_validate.py', workspace,
            inputs=inputs, nstruct=nstruct,
            max_runtime=args['--max-runtime'],
            max_memory=args['--max-memory'],
            test_run=args['--test-run'],
    )

