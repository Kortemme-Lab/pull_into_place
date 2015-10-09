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

if __name__ == '__main__':
    from tools import docopt, scripting
    from libraries import pipeline

    with scripting.catch_and_print_errors():
        args = docopt.docopt(__doc__)
        pipeline.fetch_data(
                args['<directory>'],
                args['--remote'],
                args['--include-logs'],
                args['--dry-run'],
        )



