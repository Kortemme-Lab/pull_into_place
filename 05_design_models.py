#!/usr/bin/env python2

"""\
Find sequences to stabilize the backbone models built previously.

Usage: 05_fixbb_design.py <name> <round> [options]

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

if __name__ == '__main__':
    from tools import docopt, scripting, cluster
    from libraries import workspaces, big_job

    with scripting.catch_and_print_errors():
        args = docopt.docopt(__doc__)
        cluster.require_chef()

        # Setup the workspace.

        workspace = workspaces.AllFixbbDesigns(args['<name>'], args['<round>'])
        workspace.make_dirs()
        workspace.check_paths()

        if args['--clear'] or args['--test-run']:
            workspace.clear_outputs()

        # Submit the design job.

        inputs = workspace.unclaimed_inputs
        nstruct = len(inputs) * int(args['--nstruct'])

        big_job.submit(
                'kr_fixbb.py', workspace,
                inputs=inputs, nstruct=nstruct,
                max_runtime=args['--max-runtime'],
                test_run=args['--test-run']
        )
