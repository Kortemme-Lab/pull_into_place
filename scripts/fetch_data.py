#!/usr/bin/env python2

"""\
Copy design files from a remote source.  A common application is to copy 
simulation results from the cluster to a workstation for analysis.  The given 
directory must be contained within a directory created by 01_setup_design.

Usage: fetch_data.py [options] <directory>

Options:
    --remote URL, -r URL
        Specify the URL to fetch data from.  You can put this value in a file 
        called "rsync_url" in the local workspace if you don't want to specify 
        it on the command-line every time.

    --include-logs, -i
        Fetch log files (i.e. stdout and stderr) in addition to everything 
        else.  Note that these files are often quite large, so this may take 
        significantly longer.

    --dry-run, -d
        Output rsync command that would be used to fetch data.
        
"""

def fetch_data(directory, remote_url=None, include_logs=False, dry_run=False):
    import os, subprocess
    from libraries import pipeline

    # Try to figure out the remote URL from the given directory, if a 
    # particular URL wasn't given.

    if remote_url is None:
        try:
            workspace = pipeline.workspace_from_dir(directory)
            remote_url = workspace.rsync_url
        except pipeline.WorkspaceNotFound:
            print "No remote URL specified."

    # Make sure the given directory is actually a directory.  (It's ok if it 
    # doesn't exist; rsync will create it.)

    if os.path.exists(directory) and not os.path.isdir(directory):
        print "Skipping {}: not a directory.".format(directory)
        return

    # Compose an rsync command to copy the files in question.  Then either run 
    # or print that command, depending on what the user asked for.

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
    if dry_run:
        print ' '.join(rsync_command)
    else:
        subprocess.call(rsync_command)

if __name__ == '__main__':
    from tools import docopt, scripting
    with scripting.catch_and_print_errors():
        args = docopt.docopt(__doc__)
        fetch_data(
                args['<directory>'],
                args['--remote'],
                args['--include-logs'],
                args['--dry-run'],
        )



