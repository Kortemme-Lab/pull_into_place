#!/usr/bin/env python2

"""\
Show various distance metrics for all proteins in a given directory.  The 
directory must be contained within a directory created by 01_setup_design.

Usage: show_distances.py <directory> [--recalc]

Options:
    -f, --recalc     Force the cache to be regenerated.
"""

from tools import docopt
from libraries import metrics

arguments = docopt.docopt(__doc__)
print metrics.load(arguments['<directory>'], not arguments['--recalc'])

