#!/usr/bin/env python2

"""\
Find sequences that stabilize the backbone models built previously.  The same 
resfile that was used for the model building step is used again for this step.  
Note that the model build step already includes some design.  The purpose of 
this step is to expand the number of designs for each backbone model.

Usage: 05_design_models.py <name> <round> [options]

Options:
    --nstruct NUM, -n NUM   [default: 100]
        The number of design jobs to run.

    --max-runtime TIME      [default: 0:30:00]
        The runtime limit for each design job.  The default value is 
        set pretty low so that the short queue is available by default.  This 
        should work fine more often than not, but you also shouldn't be 
        surprised if you need to increase this.

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
    nstruct = len(inputs) * int(args['--nstruct'])

    if not inputs:
        print "No inputs available."
        raise SystemExit

    # Submit the design job.

    big_job.submit(
            'kr_design.py', workspace,
            inputs=inputs, nstruct=nstruct,
            max_runtime=args['--max-runtime'],
            max_memory=args['--max-memory'],
            test_run=args['--test-run']
    )
