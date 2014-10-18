#!/usr/bin/env python2

"""\
Find sequences to stabilize the backbone models built previously.

Usage: 05_fixbb_design.py <name> <round>
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

        if args['--clear']:
            workspace.clear_designs()

        # Pick which models to design (to avoid duplicating effort).

        inputs = set(workspace.input_paths)

        for path in workspace.all_job_params_paths:
            params = big_job.read_params(path)
            inputs -= set(params['inputs'])

        # Submit the design job.

        big_job.submit(
                'kr_fixbb.py', workspace,
                inputs=sorted(inputs),
                nstruct=args['--nstruct'] * len(inputs)
                max_runtime=args['--max-runtime'],
                test_run=args['test-run']
        )



