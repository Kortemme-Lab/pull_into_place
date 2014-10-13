#!/usr/bin/env python2

"""\
Copy design files to a remote destination.  A common application is to copy 
input files onto the cluster before starting big jobs.

Usage: push_to_cluster.py <directory>
"""

import os, subprocess
from tools import docopt
from libraries import workspaces

arguments = docopt.docopt(__doc__)
directory = arguments['<directory>']
workspace = workspaces.from_directory(directory)

rsync_command = [
        'rsync', '-avr',
        '--exclude', 'rosetta',
        directory + '/', os.path.join(workspace.remote_path, directory),
]
subprocess.call(rsync_command)
