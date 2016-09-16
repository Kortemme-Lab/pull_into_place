#!/usr/bin/env python2

"""\
Cache various distance and score metrics for each model in the given directory.
After being cached, a handful of these metrics are printed to the terminal to 
show that things are working as expected.

Usage:
    pull_into_place cache_models <directory> [options]

Options:
    -r PATH, --restraints PATH
        Specify a restraints file that can be used to calculate the "restraint 
        distance" metric.  If the directory specified above was created by the 
        01_setup_pipeline script, this flag is optional and will default to the 
        restraints used in that pipeline.
        
    -f, --recalc
        Force the cache to be regenerated.
"""

from klab import docopt, scripting
from .. import structures

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    print structures.load(
            args['<directory>'],
            args['--restraints'],
            not args['--recalc']).head()

