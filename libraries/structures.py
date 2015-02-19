#!/usr/bin/env python2

"""\
This module provides a function that will read a directory of PDB files and 
return a pandas data frame containing a number of score, distance, and sequence 
metrics for each structure.  This information is also cached, because it takes 
a while to calculate up front.  Note that the cache files are pickles and seem 
to depend very closely on the version of pandas used to generate them.  For 
example, caches generated with pandas 0.15 can't be read by pandas 0.14.
"""

import sys, os, re, glob, collections, gzip
import numpy as np, scipy as sp, pandas as pd
from . import pipeline

cache_basename = 'distances.pkl'

def load(pdb_dir, restraints_path=None, use_cache=True, job_report=None):
    """
    Return a variety of score and distance metrics for the structures found in 
    the given directory.  As much information as possible will be cached.  Note 
    that new information will only be calculated for file names that haven't 
    been seen before.  If a file changes or is deleted, the cache will not be 
    updated to reflect this and you may be presented with stale data.
    """

    # If no restraints are explicitly provided, the given directory must be a 
    # workspace.  (Every workspace can provide a path to a restraints file.)

    if restraints_path is None:
        workspace = pipeline.workspace_from_dir(pdb_dir)
        restraints_path = workspace.restraints_path

    # Find all the structures in the given directory, then decide which have 
    # already been cached and which haven't.

    pdb_paths = glob.glob(os.path.join(pdb_dir, '*.pdb.gz'))
    base_pdb_names = set(os.path.basename(x) for x in pdb_paths)
    cache_path = os.path.join(pdb_dir, cache_basename)

    if use_cache and os.path.exists(cache_path):
        cached_records = pd.read_pickle(cache_path).to_dict('records')
        cached_paths = set(x['path'] for x in cached_records)
        uncached_paths = [
                pdb_path for pdb_path in pdb_paths
                if os.path.basename(pdb_path) not in cached_paths]
    else:
        cached_records = []
        uncached_paths = pdb_paths

    # Calculate socre and distance metrics for the uncached paths.

    uncached_records = read_and_calculate(uncached_paths, restraints_path)

    # Report how much work had to be done.

    if job_report is not None:
        job_report['new_records'] = len(uncached_records)
        job_report['old_records'] = len(cached_records)

    # Combine the cached and uncached data into a single data frame, use it to 
    # update the cache, then return the data frame.

    distances = pd.DataFrame(cached_records + uncached_records)
    if len(distances) > 0: distances.to_pickle(cache_path)
    return distances

def read_and_calculate(pdb_paths, restraints_path):
    """
    Calculate a variety of score and distance metrics for the given structures.
    """

    # Parse the given restraints file.  The restraints definitions are used to 
    # calculate the "restraint_dist" metric, which reflects how well each 
    # structure achieves the desired geometry. Note that this is calculated 
    # whether or not restraints were used to create the structures in question.  
    # For example, the validation runs don't use restraints but the restraint 
    # distance is a very important metric for deciding which designs worked.

    Restraint = collections.namedtuple('R', 'atom_name residue_id position')
    restraints = []

    with open(restraints_path) as file:
        for line in file:
            if line.startswith('CoordinateConstraint'):
                fields = line.split()
                restraint = Restraint(
                        atom_name=fields[1],
                        residue_id=fields[2],
                        position=xyz_to_array(fields[5:8]))
                restraints.append(restraint)

            elif not line.strip():
                pass

            else:
                print "Skipping unrecognized restraint: '{}...'".format(line[:46])

    score_table_pattern = re.compile(r'^[A-Z]{3}(?:_[A-Z])?_([1-9]+) ')

    # Calculate score and distance metrics for each structure.

    records = []
    from scipy.spatial.distance import euclidean
    from tools.bio.basics import residue_type_3to1_map

    for i, path in enumerate(pdb_paths):
        record = {'path': os.path.basename(path)}
        sequence = ""
        last_residue_id = None
        dunbrack_index = None
        dunbrack_scores = []
        restraint_distances = []

        # Update the user on our progress, because this is often slow.

        sys.stdout.write("\rReading '{}' [{}/{}]".format(
            os.path.dirname(path), i+1, len(pdb_paths)))
        sys.stdout.flush()

        # Read the PDB file, which we are assuming is gzipped.

        try:
            with gzip.open(path) as file:
                lines = file.readlines()
        except IOError:
            print "\nFailed to read '{}'".format(path)
            continue

        # Get different information from different lines in the PDB file.  Some 
        # of these lines are specific to different simulations.

        for line in lines:
            score_table_match = \
                    dunbrack_index and score_table_pattern.match(line)

            if line.startswith('total_score'):
                record['total_score'] = float(line.split()[1])

            elif line.startswith('pose'):
                # This is an alternative way to get at the total score.  Only 
                # poses generated by loop modeling will have the 'total_score' 
                # line.  In those structures, the 'pose' line will always come 
                # first and so the 'total_score' will be what's actually used.  
                # This is good, because 'total_score' is never rescored while
                # 'pose' is, so 'pose' may be less accurate in some cases.
                record['total_score'] = float(line.split()[1])

            elif line.startswith('delta_buried_unsats'):
                record['buried_unsat_score'] = float(line.split()[1])

            elif line.startswith('label'):
                fields = line.split()
                dunbrack_index = fields.index('fa_dun')

            elif score_table_match:
                residue_id = score_table_match.group(1)
                for restraint in restraints:
                    if restraint.residue_id == residue_id:
                        dunbrack_score = float(line.split()[dunbrack_index])
                        dunbrack_scores.append(dunbrack_score)
                        break

            elif line.startswith('delta_buried_unsats'):
                record['buried_unsat_score'] = float(line.split()[1])

            elif line.startswith('loop_backbone_rmsd'):
                record['loop_dist'] = float(line.split()[1])

            elif line.startswith('ATOM'):
                atom_name = line[12:16].strip()
                residue_id = line[22:26].strip()
                residue_name = line[17:20].strip()

                # Keep track of this model's sequence.

                if residue_id != last_residue_id:
                    sequence += residue_type_3to1_map.get(residue_name, 'X')
                    last_residue_id = residue_id
                
                # See if this atom was restrained.

                for restraint in restraints:
                    if (restraint.residue_id == residue_id and
                            restraint.atom_name == atom_name):
                        position = xyz_to_array(line[30:54].split())
                        distance = euclidean(restraint.position, position)
                        restraint_distances.append(distance)

        record['sequence'] = sequence
        record['dunbrack_score'] = np.max(dunbrack_scores)
        record['restraint_dist'] = np.mean(restraint_distances)
        records.append(record)

    if pdb_paths:
        sys.stdout.write('\n')

    return records

def xyz_to_array(xyz):
    return np.array([float(x) for x in xyz])


