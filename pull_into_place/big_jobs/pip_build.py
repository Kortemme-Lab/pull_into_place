#!/usr/bin/env python2

#$ -S /usr/bin/python
#$ -l mem_free=1G
#$ -l arch=linux-x64
#$ -l netapp=1G
#$ -cwd

from pull_into_place import big_jobs

workspace, job_info = big_jobs.initiate()
big_jobs.run_rosetta(
        workspace, job_info,
        use_resfile=True,
        use_restraints=True,
        use_fragments=True,
)
big_jobs.debrief()
