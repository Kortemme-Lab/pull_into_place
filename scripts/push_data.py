#!/usr/bin/env python2

"""\
Copy design files to a remote destination.  A common application is to copy 
input files onto the cluster before starting big jobs.

Usage: push_to_cluster.py [options] <remote> <directories>...

Options:
    -r, --recursive
        Indicate that directories should be recursively synced.
"""

import os, subprocess
from tools import docopt

arguments = docopt.docopt(__doc__)
remote = arguments['<remote>']
directories = arguments['<directories>']

for directory in directories:
    rsync_command = [
            'rsync', '-avr' if arguments['--recursive'] else '-av',
            directory, os.path.join(remote, directory)
    ]
    print ' '.join(rsync_command)
    subprocess.call(rsync_command)

