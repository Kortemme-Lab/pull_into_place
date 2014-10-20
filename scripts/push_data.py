#!/usr/bin/env python2

"""\
Copy design files to a remote destination.  A common application is to copy 
input files onto the cluster before starting big jobs.

Usage: push_to_cluster.py <directory>

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
            directory + '/', os.path.join(remote_url, directory),
    ]
    subprocess.call(rsync_command)
