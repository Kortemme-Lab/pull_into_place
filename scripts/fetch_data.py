#!/usr/bin/env python2

"""\
Copy design files from a remote source.  A common application is to copy 
simulation results from the cluster to a workstation for analysis.  The given 
directory must be contained within a directory created by 01_setup_design.

Usage: fetch_data.py [options] <directory>

Options:
    --remote URL, -r URL
        
"""

import os, subprocess
from tools import docopt, scripting
from libraries import pipeline

with scripting.catch_and_print_errors():
    arguments = docopt.docopt(__doc__)
    directory = arguments['<directory>']

    try:
        workspace = pipeline.workspace_from_dir(directory)
        remote_url = workspace.rsync_url
    except pipeline.WorkspaceNotFound:
        remote_url = arguments['--remote']
        if remote_url is None:
            scripting.print_error_and_die("No remote host specified.")

    rsync_command = [
            'rsync', '-avr',
            '--exclude', 'rosetta', '--exclude', 'rsync_url',
            '--exclude', 'stdout', '--exclude', 'stderr',
            os.path.join(remote_url, directory) + '/', directory
    ]
    subprocess.call(rsync_command)


