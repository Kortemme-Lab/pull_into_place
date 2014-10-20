#!/usr/bin/env python2

"""\
Build models satisfying the design goal.  Only the regions of backbone 
specified by the loop file are allowed to move and only the residues specified 
in the resfile are allowed to design.  The design goal is embodied by the 
restraints specified in the restraints file.

Usage: 03_build_restrained_models.py <name> [options]

Options:
    --nstruct NUM, -n NUM   [default: 10000]
        The number of jobs to run.  The more backbones are generated here, the 
        better the rest of the pipeline will work.  With too few backbones, you 
        can run into a lot of issues with degenerate designs.
        
    --max-runtime TIME      [default: 12:00:00]
        The runtime limit for each model building job.

    --test-run
        Run on the short queue with a limited number of iterations.  This 
        option automatically clears old results.

    --clear
        Clear existing results before submitting new jobs.
"""

from libraries import workspaces, big_job
from tools import docopt, scripting, cluster

with scripting.catch_and_print_errors():
    arguments = docopt.docopt(__doc__)
    cluster.require_chef()

    workspace = workspaces.AllRestrainedModels(arguments['<name>'])
    workspace.check_paths()
    workspace.make_dirs()

    if arguments['--clear'] or arguments['--test-run']:
        workspace.clear_outputs()

    big_job.submit(
            'kr_build.py', workspace,
            nstruct=arguments['--nstruct'],
            max_runtime=arguments['--max-runtime'],
            test_run=arguments['--test-run']
    )
