#!/usr/bin/env python2

"""\
Copy design files from a remote source.  A common application is to copy 
simulation results from the cluster to a workstation for analysis.  The given 
directory must be contained within a directory created by 01_setup_design.

Usage: fetch_data.py [options] <directory>

Options:
    --remote URL, -r URL
    --include-logs
        
"""

def fetch_data(directory, remote_url=None, include_logs=False):
    import os, subprocess
    from libraries import pipeline

    if remote_url is None:
        workspace = pipeline.workspace_from_dir(directory)
        remote_url = workspace.rsync_url

    rsync_command = [
            'rsync', '-avr',
            '--exclude', 'rosetta', '--exclude', 'rsync_url',
    ]
    if not include_logs:
        rsync_command += [
                '--exclude', 'stdout',
                '--exclude', 'stderr',
                '--exclude', '*.sc',
        ]
    rsync_command += [
            os.path.join(remote_url, directory) + '/', directory
    ]
    subprocess.call(rsync_command)

if __name__ == '__main__':
    from tools import docopt, scripting
    with scripting.catch_and_print_errors():
        args = docopt.docopt(__doc__)
        fetch_data(args['<directory>'], args['--remote'], args['--include-logs'])



