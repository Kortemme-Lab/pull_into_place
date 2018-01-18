#!/usr/bin/env python2

"""\
This module provides a function that will read a directory of PDB files and
return a pandas data frame containing a number of score, distance, and sequence
metrics for each structure.  This information is also cached, because it takes
a while to calculate up front.  Note that the cache files are pickles and seem
to depend very closely on the version of pandas used to generate them.  For
example, caches generated with pandas 0.15 can't be read by pandas 0.14.
"""

import sys, os, re, glob, collections, gzip, re, yaml
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
    filter_path = workspace.filters_list

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

    #Restraint = collections.namedtuple('R', 'restraint_type atom1 atom2 atom3 atom4 atom1_pose atom2_pose atom3_pose atom4_pose restraint_value position')
    restraints = []
    filter_list = []
    with open(workspace.restraints_path) as file:
        for line in file:
            if line.startswith('CoordinateConstraint'):
                fields = line.split()
                restraint = {}
                restraint['atom1'] = [fields[1],fields[2],None]
                restraint['restraint_value'] = fields[9]
                restraint['position'] = xyz_to_array(fields[5:8])
                restraint['restraint_type'] = fields[0]
                """
                restraint = Restraint(
                        atom1=[fields[1],fields[2]],
                        restraint_value = fields[9],
                        position=xyz_to_array(fields[5:8]),
                        atom2=None,
                        atom3=None,
                        atom4=None,
                        restraint_type=fields[0],
                        atom1_pose=None,
                        atom2_pose=None,
                        atom3_pose=None,
                        atom4_pose=None
                        )
                """
                restraints.append(restraint)
            elif line.startswith('AtomPair'):
                fields = line.split()
                restraint = {}
                restraint['atom1'] = [fields[1],fields[2],None]
                restraint['atom2'] = [fields[3],fields[4],None]
                restraint['restraint_value'] = fields[6]
                restraint['restraint_type'] = fields[0]
                """
                restraint = Restraint (
                        atom1=[fields[1],fields[2]],
                        atom2=[fields[3],fields[4]],
                        restraint_value=fields[6],
                        atom3=None,
                        atom4=None,
                        restraint_type=fields[0],
                        atom1_pose=None,
                        atom2_pose=None,
                        atom3_pose=None,
                        atom4_pose=None,
                        position=None
                )
                """
                restraints.append(restraint)
            elif line.startswith('NamedAngle'):
                fields = line.split()
                restraint = {}
                restraint['atom1'] = [fields[1],fields[2],None]
                restraint['atom2'] = [fields[3],fields[4],None]
                restraint['atom3'] = [fields[5],fields[6],None]
                restraint['restraint_value'] = fields[8]
                restraint['restraint_type'] = fields[0]
                """
                restraint = Restraint (
                        atom1=[fields[1],fields[2]],
                        atom2=[fields[3],fields[4]],
                        atom3=[fields[5],fields[6]],
                        restraint_value=fields[8],
                        atom4=None,
                        restraint_type=fields[0],
                        atom1_pose=None,
                        atom2_pose=None,
                        atom3_pose=None,
                        atom4_pose=None,
                        position=None
                )
                """
                restraints.append(restraint)
            elif line.startswith('Dihedral'):
                fields = line.split()
                restraint = {}
                restraint['atom1'] = [fields[1],fields[2],None]
                restraint['atom2'] = [fields[3],fields[4],None]
                restraint['atom3'] = [fields[5],fields[6],None]
                restraint['atom4'] = [fields[7],fields[8],None]
                restraint['restraint_value'] = fields[10]
                restraint['restraint_type'] = fields[0]
                """
                restraint = Restraint (
                        atom1=[fields[1],fields[2]],
                        atom2=[fields[3],fields[4]],
                        atom3=[fields[5],fields[6]],
                        atom4=[fields[7],fields[8]],
                        restraint_value = fields[10],
                        restraint_type=fields[0],
                        atom1_pose=None,
                        atom2_pose=None,
                        atom3_pose=None,
                        atom4_pose=None,
                        position=None
                )
                """
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
                    for key in restraint:
                        try:
                            if restraint[key][1] == residue_id:
                                dunbrack_score = float(line.split()[dunbrack_index])
                                dunbrack_scores.append(dunbrack_score)
                                break
                        except:
                            pass

            elif line.startswith('EXTRA_SCORE_'):
                filter_value = float(line.rsplit()[-1:][0])
                filter_name = " ".join(line.rsplit()[:-1])[12:]
                record[filter_name] = filter_value
                if filter_name not in filter_list:
                    filter_list.append(filter_name)

            elif line.startswith('delta_buried_unsats'):
                record['buried_unsat_score'] = float(line.split()[1])

            elif line.startswith('loop_backbone_rmsd'):
                record['loop_dist'] = float(line.split()[1])

            elif line.startswith('ATOM') or line.startswith('HETATM'):
                atom_name = line[12:16].strip()
                residue_id = line[22:26].strip()
                residue_name = line[17:20].strip()

                # Keep track of this model's sequence.

                if residue_id != last_residue_id and line.startswith('ATOM'):
                    sequence += residue_type_3to1_map.get(residue_name, 'X')
                    last_residue_id = residue_id

                # See if this atom was restrained.

                for restraint in restraints:
                    if restraint['restraint_type'] == 'CoordinateConstraint':
                        try:
                            if (restraint['atom1'][1] == residue_id and
                                    restraint['atom1'][0] == atom_name):
                                restraint = restraint._replace(atom1_pose = xyz_to_array(line[30:54].split()))
                        except:
                            print "Error: Something went wrong with your coordinate constraints."
                            pass
                    else:
                        for key in restraint:
                            try:
                                if restraint[key][0] == atom_name and restraint[key][1] == residue_id:
                                    restraint[key][2] = xyz_to_array(line[30:54].split())
                            except:
                                print "Error: Something went wrong with your constraints."
                                pass


        filter_path = workspace.filters_list
        with open(filter_path, 'r+') as file:
            filter_list_cached = yaml.load(file)
            if not filter_list_cached:
                filter_list_cached = []
            new_filters = []
            for f in filter_list:
                if f not in filter_list_cached:
                    new_filters.append(f)
        if new_filters:
            with open(filter_path, 'w') as file:
                filter_list_to_cache = filter_list_cached + new_filters
                yaml.dump(filter_list_to_cache,file)

        record['sequence'] = sequence
        if dunbrack_scores:
            record['dunbrack_score'] = np.max(dunbrack_scores)
        restraint_distances = parse_distance_restraints(restraints)
        if restraint_distances:
            record['restraint_dist'] = np.max(restraint_distances)
        restraint_angles = parse_angle_restraints(restraints)
        if restraint_angles:
            record['restraint_angles'] = np.max(restraint_angles)
        restraint_dihedrals = parse_dihedral_restraints(restraints)
        if restraint_dihedrals:
            record['restraint_dihedrals'] = np.max(restraint_dihedrals)
        if restraint_angles and restraint_dihedrals and restraint_distances:
            record['restraint_sum'] = record['restraint_dist'] + record['restraint_angles'] + record['restraint_dihedrals']

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

def parse_filter_name(name):
    found = re.search(r"\[\[(.*?)\]\]",name)
    direction = None
    if found:
        title = re.sub(' +',' ',re.sub(r'\[\[(.*?)\]\]','',name).rstrip())
        direction = found.group(1)
    else:
        title = name
    return title, direction

def parse_distance_restraints(restraints):
    from scipy.spatial.distance import euclidean
    restraint_distances = []
    for restraint in restraints:
        if restraint['restraint_type'] == 'CoordinateConstraint':
            distance = euclidean(restraint['atom1'][2], restraint['position'])
            restraint_distances.append(abs(distance - float(restraint['restraint_value'])))
        elif restraint['restraint_type'] == 'AtomPair':
            try:
                distance = euclidean(restraint['atom1'][2], restraint['atom2'][2])
                restraint_distances.append(abs(distance - float(restraint['restraint_value'])))
            except:
                pass
    return restraint_distances

def parse_angle_restraints(restraints):
    restraint_angle_satisfaction = []
    for restraint in restraints:
        temp_angles = []
        if restraint['restraint_type'] == 'NamedAngle':
            try:
                A = restraint['atom1'][2]
                B = restraint['atom2'][2]
                C = restraint['atom3'][2]
                # vectors between points:
                ab = A - B
                cb = C - B
                angle = np.arccos((np.dot(ab, cb)) / (np.sqrt(ab[0]**2 + ab[1]**2 + ab[2]**2) * np.sqrt(cb[0]**2 + cb[1]**2 + cb[2]**2)))
                rv = float(restraint['restraint_value'])
                temp_angles.append(abs(angle - rv))
                temp_angles.append(abs((angle - 2 * np.pi) - rv))
                temp_angles.append(abs((angle + 2 * np.pi) - rv))
                restraint_angle_satisfaction.append(np.min(temp_angles))
            except:
                pass
    return restraint_angle_satisfaction

def parse_dihedral_restraints(restraints):
    restraint_dihedrals = []
    for restraint in restraints:
        temp_dihedrals = []
        if restraint['restraint_type'] == 'Dihedral':
            try:
                p1 = restraint['atom1'][2]
                p2 = restraint['atom2'][2]
                p3 = restraint['atom3'][2]
                p4 = restraint['atom4'][2]

                vector1 = -1.0 * (p2 - p1)
                vector2 = p3 - p2
                vector3 = p4 - p3

                # Normalize vector so as not to influence magnitude of vector rejections
                vector2 /= np.linalg.norm(vector2)

                # Vector rejections:
                # v = projection of vector1 onto plane perpendicular to vector2
                #   = vector1 - component that aligns with vector2
                # w = projection of vector3 onto plane perpendicular to vector2
                #   = vector3 - component that aligns with vector2
                v = vector1 - np.dot(vector1, vector2) * vector2
                w = vector3 - np.dot(vector3, vector2) * vector2

                # Angle between v and w in a plane is the torsion angle.
                # v and w not normalized but we'll use tan so it doesn't matter.
                x = np.dot(v, w)
                y = np.dot(np.cross(vector2,v),w)
                principal_dihedral = np.arctan2(y,x)
                rv = float(restraint['restraint_value'])
                temp_dihedrals.append(abs(principal_dihedral -rv))
                temp_dihedrals.append(abs((principal_dihedral - 2 * np.pi) - rv))
                temp_dihedrals.append(abs((principal_dihedral + 2 * np.pi) - rv))
                restraint_dihedrals.append(np.min(temp_dihedrals))
            except:
                pass
    return restraint_dihedrals


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
