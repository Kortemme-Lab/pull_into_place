#!/usr/bin/env python2

"""\
Find sequences that stabilize the backbone models built previously.  The same 
resfile that was used for the model building step is used again for this step.  
Note that the model build step already includes some design.  The purpose of 
this step is to expand the number of designs for each backbone model.

Usage: 05_design_models.py <name> <round> [options]

Options:
    --nstruct NUM, -n NUM   [default: 500]
        The number of design jobs to run.

    --max-runtime TIME      [default: 6:00:00]
        The runtime limit for each design job.

    --max-memory MEM        [default: 1G]
        The memory limit for each design job.

    --test-run
        Run on the short queue with a limited number of iterations.  This 
        option automatically clears old results.

    --clear
        Clear existing results before submitting new jobs.
"""

from tools import docopt, scripting, cluster
from libraries import pipeline, big_job

with scripting.catch_and_print_errors():
    args = docopt.docopt(__doc__)
    cluster.require_chef()

    # Setup the workspace.

    workspace = pipeline.FixbbDesigns(args['<name>'], args['<round>'])
    workspace.make_dirs()
    workspace.check_paths()

    if args['--clear'] or args['--test-run']:
        workspace.clear_outputs()

    # Decide which inputs to use.

    inputs = workspace.unclaimed_inputs
    designs_per = int(args['--nstruct']) if not args['--test-run'] else 2

    if not inputs:
        print "All inputs have been claimed."
        raise SystemExit

    # Submit the design job.

    big_job.submit(
            'kr_design.py', workspace,
            inputs=inputs, nstruct=len(inputs), designs_per=designs_per,
            max_runtime=args['--max-runtime'],
            max_memory=args['--max-memory'],
            test_run=args['--test-run']
    )
