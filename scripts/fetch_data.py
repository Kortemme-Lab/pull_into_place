#!/usr/bin/env python2

"""\
Copy design files from a remote source.  A common application is to copy 
simulation results from the cluster to a workstation for analysis.  The given 
directory must be contained within a directory created by 01_setup_design.

Usage: fetch_data.py [options] <directory>
"""

import os, subprocess
from tools import docopt, scripting
from libraries import pipeline

with scripting.catch_and_print_errors():
    arguments = docopt.docopt(__doc__)
    directory = arguments['<directory>']
    workspace = pipeline.workspace_from_dir(directory)

    rsync_command = [
            'rsync',
            '-avr' if workspace.rsync_recursive_flag else '-av',
    ]
    for pattern in workspace.rsync_include_patterns:
        rsync_command += ['--include', pattern]

    for pattern in workspace.rsync_exclude_patterns:
        rsync_command += ['--exclude', pattern]
        
    rsync_command += [
            os.path.join(workspace.rsync_url, directory) + '/', directory
    ]
    subprocess.call(rsync_command)


