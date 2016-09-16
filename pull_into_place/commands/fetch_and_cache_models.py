#!/usr/bin/env python2

"""\
Download models from a remote host then cache a number of distance and score 
metrics for each one.  This script is meant to be called periodically during 
long running jobs, to reduce the amount of time you have to spend waiting to 
build the cache at the end.

Usage:
    pull_into_place fetch_and_cache_models <directory> [options]

Options:
    --remote URL, -r URL
        Specify the URL to fetch data from.  You can put this value in a file 
        called "rsync_url" in the local workspace if you don't want to specify 
        it on the command-line every time.

    --include-logs, -i
        Fetch log files (i.e. stdout and stderr) in addition to everything 
        else.  Note that these files are often quite large, so this may take 
        significantly longer.

    --keep-going, -k
        Keep attempting to fetch and cache new models until you press Ctrl-C.  
        You can run this command with this flag at the start of a long job, and 
        it will incrementally cache new models as they are produced.
"""

from klab import docopt, scripting
from .. import pipeline

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    directories = []

    if args['--keep-going']:
        while True:
            pipeline.fetch_and_cache_data(
                    args['<directory>'],
                    args['--remote'],
                    args['--include-logs'],
            )
    else:
        pipeline.fetch_and_cache_data(
                args['<directory>'],
                args['--remote'],
                args['--include-logs'],
        )
