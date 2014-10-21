#!/usr/bin/env python2

"""\
Show various distance metrics for all proteins in a given directory.  The 
directory must be contained within a directory created by 01_setup_pipeline.

Usage: show_distances.py <directory> [--recalc]

Options:
    -f, --recalc     Force the cache to be regenerated.
"""

from tools import docopt
from libraries import pipeline, structures

arguments = docopt.docopt(__doc__)
workspace = pipeline.workspace_from_dir(arguments['<directory>'])

print structures.load(
        arguments['<directory>'], 
        workspace.restraints_path,
        not arguments['--recalc']).head()

