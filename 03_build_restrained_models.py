#!/usr/bin/env python2

"""\
Build models satisfying the design goal.  Only the regions of backbone 
specified by the loop file are allowed to move and only the residues specified 
in the resfile are allowed to design.  The design goal is embodied by the 
restraints specified in the restraints file.

Usage: 02_build_restrained_models.py <name> [options]

Options:
    --nstruct NUM -n NUM
        The number of jobs to run.  The greater diversity of models generated 
        Number of jobs to run.  It's very important to get a diversity of 
        models at this stage in the pipeline, so choose a big number [default: 
        10000].

    --max-runtime TIME
        The runtime limit for each model building job.  
        Max runtime.  May ned to increase this for certain inputs [default: 
        12:00:00].
        
    --test-run
        Run on the short queue with a limited number of iterations.  Useful for 
        debugging.
"""

if __name__ == '__main__':
    from libraries import workspaces, big_job
    from tools import docopt, scripting, cluster

    arguments = docopt.docopt(__doc__)
    cluster.require_chef()

    workspace = workspaces.AllRestrainedModels(arguments['<name>'])
    workspace.require_standard_paths()
    workspace.clear_models()

    big_job.submit(
            'workhorses/kr_build.py', workspace,
            nstruct=arguments['--nstruct'],
            max_runtime=arguments['--max-runtime'],
            test_run=arguments['--test-run']
    )


