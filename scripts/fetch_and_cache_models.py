#!/usr/bin/env python2

"""\
Download models from a remote host then cache a number of distance and score 
metrics for each one.  This script is meant to be called periodically during 
long running jobs, to reduce the amount of time you have to spend waiting to 
build the cache at the end.

Usage: fetch_and_cache_models.py <directories>... [options]

Options:
    --remote URL
    --include-logs
    --restraints PATH
    --loop
"""

from __future__ import division

import os
from tools import docopt, scripting
from libraries import structures
from fetch_data import fetch_data

with scripting.catch_and_print_errors():
    args = docopt.docopt(__doc__)
    directories = []
    keep_going = True

    for directory in args['<directories>']:
        if os.path.isdir(directory): directories.append(directory)
        else: print "Skipping '{}': not a directory.".format(directory)

    while keep_going:
        for directory in directories:
            fetch_data(directory, args['--remote'], args['--include-logs'])
            structures.load(directory, args['--restraints'])
        keep_going = args['--loop']
