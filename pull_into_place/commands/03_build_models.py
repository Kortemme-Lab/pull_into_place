#!/usr/bin/env python2

"""\
Build models satisfying the design goal.  Only the regions of backbone 
specified by the loop file are allowed to move and only the residues specified 
in the resfile are allowed to design.  The design goal is embodied by the 
restraints specified in the restraints file.

Usage:
    pull_into_place 03_build_models <workspace> [options]

Options:
    --nstruct NUM, -n NUM   [default: 10000]
        The number of jobs to run.  The more backbones are generated here, the 
        better the rest of the pipeline will work.  With too few backbones, you 
        can run into a lot of issues with degenerate designs.
        
    --max-runtime TIME      [default: 12:00:00]
        The runtime limit for each model building job.

    --max-memory MEM        [default: 2G]
        The memory limit for each model building job.

    --mkdir
        Make the directory corresponding to this step in the pipeline, but 
        don't do anything else.  This is useful if you want to create custom 
        input files for just this step.

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

    # Setup the workspace.

    workspace = pipeline.RestrainedModels(args['<workspace>'])
    workspace.check_paths()
    workspace.check_rosetta()
    workspace.make_dirs()

    if args['--mkdir']:
        return
    if args['--clear'] or args['--test-run']:
        workspace.clear_outputs()

    cluster.require_qsub()
    # Submit the model building job.

    big_jobs.submit(
            'pip_build.py', workspace,
            nstruct=args['--nstruct'],
            max_runtime=args['--max-runtime'],
            max_memory=args['--max-memory'],
            test_run=args['--test-run']
    )
