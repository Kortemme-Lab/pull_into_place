#!/usr/bin/env python2

#$ -S /usr/bin/python
#$ -l mem_free=1G
#$ -l arch=linux-x64
#$ -l netapp=1G
#$ -l h_core=0
#$ -cwd

from pull_into_place import big_jobs

workspace, job_info = big_jobs.initiate()

# I wasn't able to get PackRotamers to respect any restraints set on the 
# command line, so instead the restraints are set in the protocol itself.
big_jobs.run_rosetta(
        workspace, job_info,
        use_resfile=True,
)
big_jobs.debrief()
