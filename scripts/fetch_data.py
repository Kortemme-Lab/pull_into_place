#!/usr/bin/env python2

"""\
Copy design files from a remote source.  A common application is to copy 
simulation results from the cluster to a workstation for analysis.  The given 
directory must be contained within a directory created by 01_setup_design.

Usage: fetch_data.py [options] <directory>
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
        '--exclude', 'remote',
        os.path.join(workspace.remote_path, directory) + '/', directory
]
subprocess.call(rsync_command)


