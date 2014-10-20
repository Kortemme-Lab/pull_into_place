#!/usr/bin/env python2

"""\
Copy design files to a remote destination.  A common application is to copy 
input files onto the cluster before starting big jobs.

Usage: push_to_cluster.py <directory>
"""

import os, subprocess
from tools import docopt
from libraries import pipeline

arguments = docopt.docopt(__doc__)
directory = arguments['<directory>']
workspace = pipeline.workspace_from_dir(directory)

rsync_command = [
        'rsync', '-avr',
        '--exclude', 'rosetta',
        '--exclude', 'remote',
        directory + '/', os.path.join(workspace.rsync_url, directory),
]
print ' '.join(rsync_command)
subprocess.call(rsync_command)
