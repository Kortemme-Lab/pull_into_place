#!/usr/bin/env python2

"""\
Validate the designs by running unrestrained flexible backbone simulations.  
Only regions of the backbone specified by the loop file are allowed to move.  
The resfile used in the previous steps of the pipeline is not respected here; 
all residues within 10A of the loop are allowed to pack.

Usage:
    pull_into_place 08_validate_designs <workspace> <round> [options]

Options:
    --nstruct NUM, -n NUM   [default: 500]
        The number of simulations to run per design.
        
    --max-runtime TIME      [default: 24:00:00]
        The runtime limit for each validation job.

    --max-memory MEM        [default: 1G]
        The memory limit for each validation job.

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

    workspace = pipeline.ValidatedDesigns(args['<workspace>'], args['<round>'])
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

    big_jobs.submit(
            'pip_validate.py', workspace,
            inputs=inputs, nstruct=nstruct,
            max_runtime=args['--max-runtime'],
            max_memory=args['--max-memory'],
            test_run=args['--test-run'],
    )

