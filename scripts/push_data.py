#!/usr/bin/env python2

"""\
Copy design files to a remote destination.  A common application is to copy 
input files onto the cluster before starting big jobs.

Usage: push_to_cluster.py <directory>
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
            directory + '/', os.path.join(workspace.rsync_url, directory),
    ]
    subprocess.call(rsync_command)
