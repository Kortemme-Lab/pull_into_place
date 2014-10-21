#!/usr/bin/env python2

"""\
Copy design files to a remote destination.  A common application is to copy 
input files onto the cluster before starting big jobs.

Usage: push_to_cluster.py <directory> [options]

Options:
    --remote URL, -r URL
"""

def push_data(directory, remote_url=None):
    import os, subprocess
    from libraries import pipeline

    if remote_url is None:
        workspace = pipeline.workspace_from_dir(directory)
        remote_url = workspace.rsync_url

    rsync_command = [
            'rsync', '-avr',
            '--exclude', 'rosetta', '--exclude', 'rsync_url',
            '--exclude', 'stdout', '--exclude', 'stderr',
            directory + '/', os.path.join(remote_url, directory),
    ]
    subprocess.call(rsync_command)

if __name__ == '__main__':
    from tools import docopt, scripting
    with scripting.catch_and_print_errors():
        args = docopt.docopt(__doc__)
        push_data(args['<directory>'], args['--remote'])

