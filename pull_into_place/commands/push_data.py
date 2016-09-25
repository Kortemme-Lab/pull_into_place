#!/usr/bin/env python2

"""\
Copy design files to a remote destination.  A common application is to copy 
input files onto the cluster before starting big jobs.

Usage:
    pull_into_place push_data <directory> [options]

Options:
    --remote URL, -r URL
        Specify the URL to push data to.

    --dry-run, -d
        Output the rsync command that would be used to push data.
"""

from klab import docopt, scripting
from .. import pipeline

@scripting.catch_and_print_errors()
def main():
    args = docopt.docopt(__doc__)
    pipeline.push_data(args['<directory>'], args['--remote'], args['--dry-run'])

