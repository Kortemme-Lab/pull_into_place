#!/usr/bin/env python2

"""\
Run additional filters on a folder of pdbs and copy the results back
into the original pdb.

Usage:
    pull_into_place run_additional_metrics <directory> [options]

Options:
    --max-runtime TIME      [default: 12:00:00]
        The runtime limit for each design job.  The default value is
        set pretty low so that the short queue is available by default.  This
        should work fine more often than not, but you also shouldn't be
        surprised if you need to increase this.

    --max-memory MEM        [default: 2G]
        The memory limit for each design job.

    --mkdir
        Make the directory corresponding to this step in the pipeline, but 
        don't do anything else.  This is useful if you want to create custom 
        input files for just this step.

    --test-run
        Run on the short queue with a limited number of iterations.  This
        option automatically clears old results.

    --clear
        Clear existing results before submitting new jobs.

To use this class:
    1. You need to initiate it with the directory where your pdb files
    to be rerun are. 
    2. You need to use the setters for the Rosetta executable and the
    metric. 

"""

from klab import docopt, scripting, cluster
from pull_into_place import pipeline, big_jobs

   


@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    cluster.require_qsub()

    # Setup the workspace.

    workspace = pipeline.AdditionalMetricWorkspace(args['<directory>'])
    workspace.check_paths()
    workspace.check_rosetta()

    if args['--mkdir']:
        return
    if args['--clear'] or args['--test-run']:
        workspace.clear_outputs()

    # Decide which inputs to use.

    inputs = workspace.unclaimed_inputs
    nstruct = len(inputs) 

    if not inputs:
        print """\
All the input structures have already been (or are already being)
designed. If you want to rerun all the inputs from scratch, use the
--clear flag."""
        raise SystemExit

    # Submit the design job. 

    big_jobs.submit(
            'pip_add_metrics.py', workspace, 
            inputs=inputs, nstruct=nstruct,
            max_runtime=args['--max-runtime'],
            max_memory=args['--max-memory'],
            test_run=args['--test-run']
    )
