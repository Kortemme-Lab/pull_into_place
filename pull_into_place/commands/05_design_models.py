#!/usr/bin/env python2

"""\
Find sequences that stabilize the backbone models built previously.  The same 
resfile that was used for the model building step is used again for this step.  
Note that the model build step already includes some design.  The purpose of 
this step is to expand the number of designs for each backbone model.

Usage:
    pull_into_place 05_design_models <workspace> <round> [options]

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

from klab import docopt, scripting, cluster
from .. import pipeline, big_jobs

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    cluster.require_qsub()

    # Setup the workspace.

    workspace = pipeline.FixbbDesigns(args['<workspace>'], args['<round>'])
    workspace.check_paths()
    workspace.check_rosetta()
    workspace.make_dirs()

    if args['--clear'] or args['--test-run']:
        workspace.clear_outputs()

    # Decide which inputs to use.

    inputs = workspace.unclaimed_inputs
    nstruct = len(inputs) * int(args['--nstruct'])

    if not inputs:
        print """\
All the input structures have already been (or are already being) designed.  If 
you want to rerun all the inputs from scratch, use the --clear flag."""
        raise SystemExit

    # Submit the design job.

    big_jobs.submit(
            'pip_design.py', workspace,
            inputs=inputs, nstruct=nstruct,
            max_runtime=args['--max-runtime'],
            max_memory=args['--max-memory'],
            test_run=args['--test-run']
    )
