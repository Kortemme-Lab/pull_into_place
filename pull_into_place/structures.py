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

def load(pdb_dir, use_cache=True, job_report=None, require_io_dir=True):
    """
    Return a variety of score and distance metrics for the structures found in 
    the given directory.  As much information as possible will be cached.  Note 
    that new information will only be calculated for file names that haven't 
    been seen before.  If a file changes or is deleted, the cache will not be 
    updated to reflect this and you may be presented with stale data.
    """

    # Make sure the given directory seems to be a reasonable place to look for 
    # data, i.e. it exists and contains PDB files.

    if not os.path.exists(pdb_dir):
        raise IOError("'{}' does not exist".format(pdb_dir))
    if not os.path.isdir(pdb_dir):
        raise IOError("'{}' is not a directory".format(pdb_dir))
    if not os.listdir(pdb_dir):
        raise IOError("'{}' is empty".format(pdb_dir))
    if not glob.glob(os.path.join(pdb_dir, '*.pdb*')):
        raise IOError("'{}' doesn't contain any PDB files".format(pdb_dir))

    # The given directory must also be a workspace, so that the restraint file 
    # can be found and used to calculate the "restraint_dist" metric later on.

    try:
        workspace = pipeline.workspace_from_dir(pdb_dir)
    except pipeline.WorkspaceNotFound:
        raise IOError("'{}' is not a workspace".format(pdb_dir))
    if require_io_dir and not any(
            os.path.samefile(pdb_dir, x) for x in workspace.io_dirs):
        raise IOError("'{}' is not an input or output directory".format(pdb_dir))

    # Find all the structures in the given directory, then decide which have 
    # already been cached and which haven't.

    pdb_paths = glob.glob(os.path.join(pdb_dir, '*.pdb.gz'))
    base_pdb_names = set(os.path.basename(x) for x in pdb_paths)
    cache_path = os.path.join(pdb_dir, 'distances.pkl')

    if use_cache and os.path.exists(cache_path):
        try:
            cached_records = pd.read_pickle(cache_path).to_dict('records')
            cached_paths = set(x['path'] for x in cached_records)
            uncached_paths = [
                    pdb_path for pdb_path in pdb_paths
                    if os.path.basename(pdb_path) not in cached_paths]
        except:
            print "Couldn't load '{}'".format(cache_path)
            cached_records = []
            uncached_paths = pdb_paths
    else:
        cached_records = []
        uncached_paths = pdb_paths

    # Calculate score and distance metrics for the uncached paths, then combine 
    # the cached and uncached data into a single data frame.

    uncached_records = read_and_calculate(workspace, uncached_paths)
    all_records = pd.DataFrame(cached_records + uncached_records)

    # Make sure all the expected metrics were calculated.
    
    expected_metrics = [
            'total_score',
            'restraint_dist',
            'sequence',
    ]
    for metric in expected_metrics:
        if metric not in all_records:
            print all_records.keys()
            raise IOError("'{}' wasn't calculated for the models in '{}'".format(metric, pdb_dir))

    # If everything else looks good, cache the data frame so we can load faster 
    # next time.

    all_records.to_pickle(cache_path)

    # Report how many structures had to be cached, in case the caller is 
    # interested, and return to loaded data frame.

    if job_report is not None:
        job_report['new_records'] = len(uncached_records)
        job_report['old_records'] = len(cached_records)

    return all_records

def read_and_calculate(workspace, pdb_paths):
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

    with open(workspace.restraints_path) as file:
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
    from klab.bio.basics import residue_type_3to1_map

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

        if not lines:
            print "\n{} is empty".format(path)
            continue

        # Get different information from different lines in the PDB file.  Some 
        # of these lines are specific to different simulations.

        for line in lines:
            score_table_match = \
                    dunbrack_index and score_table_pattern.match(line)

            if line.startswith('pose'):
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
        if dunbrack_scores:
            record['dunbrack_score'] = np.max(dunbrack_scores)
        if restraint_distances:
            record['restraint_dist'] = np.mean(restraint_distances)
        records.append(record)

    if pdb_paths:
        sys.stdout.write('\n')

    return records

def xyz_to_array(xyz):
    """
    Convert a list of strings representing a 3D coordinate to floats and return 
    the coordinate as a ``numpy`` array.
    """
    return np.array([float(x) for x in xyz])


class Design (object):
    """
    Represent a single validated design.  Each design is associated with 500 
    scores, 500 restraint distances, and a "representative" (i.e. lowest 
    scoring) model.  The representative has its own score and restraint 
    distance, plus a path to a PDB structure.
    """

    def __init__(self, directory):
        self.directory = directory
        self.structures = load(directory)
        self.loops = pipeline.load_loops(directory)
        self.resfile = pipeline.load_resfile(directory)
        self.representative = self.rep = np.argmin(self.scores)

    def __getitem__(self, key):
        return self.structures[key]

    @property
    def scores(self):
        return self['total_score']

    @property
    def distances(self):
        return self['restraint_dist']

    @property
    def resfile_sequence(self):
        resis = sorted(int(i) for i in self.resfile.designable)
        return ''.join(self['sequence'][self.rep][i-1] for i in resis)

    @property
    def rep_path(self):
        return os.path.join(self.directory, self['path'][self.rep])

    @property
    def rep_score(self):
        return self.scores[self.rep]

    @property
    def rep_distance(self):
        return self.distances[self.rep]


class IOError (IOError):
    no_stack_trace = True

