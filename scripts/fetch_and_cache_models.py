#!/usr/bin/env python2

"""\
Simultaneously download models from a remote host and cache a number of 
distance and score metrics for each one.  This script is meant to be run 
concurrently with big cluster jobs.  As such, it continues running until no 
new structures have been processed for over an hour and it ignores hang-up 
signals on its own.

Usage: fetch_and_cache_models.py <directories>... [options]

Options:
    --remote URL
    --restraints PATH
"""

from time import time, sleep
from tools import docopt, scripting
from libraries import structures
from fetch_data import fetch_data

with scripting.catch_and_print_errors():
    args = docopt.docopt(__doc__)

    sleep_time = 5 * 60
    job_finished_time = 60 * 60
    last_activity = time()

    while time() - last_activity < job_finished_time:
        job_reports = {}

        for directory in args['<directories>']:
            report = job_reports[directory] = {}
            fetch_data(directory, args['--remote'])
            structures.load(directory, args['--restraints'], job_report=report)
            print

        for directory in job_reports:
            if job_reports[directory]['new_records'] > 0:
                last_activity = time()

        print "Sleeping..."
        sleep(sleep_time)
