#!/usr/bin/env python2

"""\
Pick the designs that are at or near the Pareto front of the given metrics to 
validate in the next step.

Usage:
    pull_into_place 06_pick_designs_to_validate
            <workspace> <round> [<picks>] [options]

Arguments:
    <picks>
        A file specifying how to pick designs.  If you don't provide a file on 
        the command line, PIP will automatically search for a file in your 
        workspace called 'picks.yml'.  Below is an example of what this file 
        should look like:

            threshold:
            - restraint_dist_e38 < 0.8
            - h_bond_to_e38_sidechain == 0
            - oversaturated_h_bonds == 0

            pareto:
            - total_score
            - restraint_dist_e38
            - max_9_residue_fragment_rmsd_c

            depth: 1
            epsilon: 0.5

Options:
    --clear, -x
        Forget about any designs that were previously picked for validation.

    --recalc, -f
        Recalculate all the metrics that will be used to choose designs.

    --dry-run, -d
        Don't actually fill in the input directory of the validation workspace.  
        Instead just report how many designs would be picked.

Metrics:
    The given metrics specify which scores will be used to construct the Pareto 
    front.  You can refer to any of the metrics available in the 'plot_funnels' 
    GUI by making the title lowercase, replacing any spaces or dashes with 
    underscores, and removing any special characters.

    In order for this to work, PIP needs to understand whether high values or 
    low values are favorable for each individual metric.  This is taken care of 
    for all the built-in metrics, but if you've added any filters to the 
    pipeline, you need to specify this by adding a short code to your filters' 
    names: "[+]" if bigger is better, or "[-]" if smaller is better.

Tuning:
    Depending on the round, you often want to validate between 50-500 designs.  
    However, there's no direct way to control exactly how many designs are in 
    the Pareto front.  Instead, you have to use the depth and epsilon options 
    to tune both the quantity and diversity of designs that are selected.

    Increasing depth increases the number of designs that are selected, 
    because it includes designs that are the given number of steps back from 
    the Pareto front.

    Increasing epsilon decreases the number of designs that are selected, but 
    increases the diversity of those designs, because it excludes designs that 
    have very similar scores across all the metrics being considered.
"""

from klab import docopt, scripting
from .. import pipeline, structures
from pprint import pprint

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    root = args['<workspace>']
    round = args['<round>']

    workspace = pipeline.ValidatedDesigns(root, round)
    workspace.check_paths()
    workspace.make_dirs()

    structures.make_picks(
            workspace, 
            args['<picks>'],
            clear=args['--clear'],
            use_cache=not args['--recalc'],
            dry_run=args['--dry-run'],
    )
