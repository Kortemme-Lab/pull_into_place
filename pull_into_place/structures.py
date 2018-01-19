#!/usr/bin/env python2
# encoding: utf-8

from __future__ import division

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
from scipy.spatial.distance import euclidean
from pprint import pprint
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
    cache_path = os.path.join(pdb_dir, 'metrics.pkl')
    metadata_path = os.path.join(pdb_dir, 'metrics.yml')

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

    metadata = {}
    if use_cache and os.path.exists(metadata_path):
        with open(metadata_path) as file:
            metadata_list = [ScoreMetadata(**x) for x in yaml.load(file)]
            metadata = {x.name: x for x in metadata_list}

    # Calculate score and distance metrics for the uncached paths, then combine
    # the cached and uncached data into a single data frame.

    uncached_records, uncached_metadata = \
            read_and_calculate(workspace, uncached_paths)

    all_records = pd.DataFrame(cached_records + uncached_records)
    metadata.update(uncached_metadata)

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
    with open(metadata_path, 'w') as file:
        yaml.dump([v.to_dict() for k,v in metadata.items()], file)

    # Report how many structures had to be cached, in case the caller is
    # interested, and return to loaded data frame.

    if job_report is not None:
        job_report['new_records'] = len(uncached_records)
        job_report['old_records'] = len(cached_records)

    return all_records, metadata

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

    restraints = parse_restraints(workspace.restraints_path)

    # Calculate score and distance metrics for each structure.

    from klab.bio.basics import residue_type_3to1_map

    records = []
    metadata = {}
    num_restraints = len(restraints) + 1
    atom_xyzs = {}
    score_table_pattern = re.compile(r'^[A-Z]{3}(?:_[A-Z])?_([1-9]+) ')

    for i, path in enumerate(pdb_paths):
        record = {'path': os.path.basename(path)}
        sequence = ""
        sequence_map = {}
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
                meta = ScoreMetadata(
                        name='total_score',
                        title='Total Score (REU)',
                        order=1,
                )
                record['total_score'] = float(line.split()[1])
                metadata[meta.name] = meta

            elif line.startswith('label'):
                fields = line.split()
                dunbrack_index = fields.index('fa_dun')

            elif score_table_match:
                residue_id = score_table_match.group(1)
                for restraint in restraints:
                    if residue_id in restraint.residue_ids:
                        dunbrack_score = float(line.split()[dunbrack_index])
                        dunbrack_scores.append(dunbrack_score)
                        break

            elif line.startswith('EXTRA_SCORE_'):
                tokens = line[len('EXTRA_SCORE_'):].rsplit(None, 1)
                meta = parse_filter(tokens[0], 5)
                record[meta.name] = float(tokens[1])
                metadata[meta.name] = meta

            elif line.startswith('delta_buried_unsats'):
                meta = ScoreMetadata(
                        name='buried_unsats',
                        title='Δ Buried Unsats',
                        order=5,
                )
                record['buried_unsats'] = float(line.split()[1])
                metadata[meta.name] = meta

            elif line.startswith('loop_backbone_rmsd'):
                meta = ScoreMetadata(
                        name='loop_rmsd',
                        title='Loop RMSD (Å)',
                        guide=1.0, lower=0.0, upper='95%', order=4,
                )
                record['loop_rmsd'] = float(line.split()[1])
                metadata[meta.name] = meta

            elif (line.startswith('ATOM') or line.startswith('HETATM')):
                atom_name = line[12:16].strip()
                residue_id = int(line[22:26].strip())
                residue_name = line[17:20].strip()

                # Keep track of this model's sequence.

                if line.startswith('ATOM'): 
                    if residue_id != last_residue_id:
                        one_letter_code = residue_type_3to1_map.get(residue_name, 'X')
                        sequence += one_letter_code
                        sequence_map[residue_id] = one_letter_code
                        last_residue_id = residue_id

                # Save the coordinate for this atom.  This will be used later 
                # to calculate restraint distances.

                atom_xyzs[atom_name, residue_id] = xyz_to_array((
                        line[30:38], line[38:46], line[46:54]))

        # Finish calculating some records that depend on the whole structure.

        record['sequence'] = sequence
        if dunbrack_scores:
            meta = ScoreMetadata(
                    name='dunbrack_score',
                    title='Dunbrack Score (REU)',
                    order=5,
            )
            record['dunbrack_score'] = np.max(dunbrack_scores)
            metadata[meta.name] = meta

        # Calculate how well each restraint was satisfied.

        restraint_distances = []
        residue_specific_restraint_distances = {}

        for restraint in restraints:
            d = restraint.distance_from_ideal(atom_xyzs)
            restraint_distances.append(d)
            for i in restraint.residue_ids:
                residue_specific_restraint_distances.setdefault(i,[]).append(d)

        if restraint_distances:
            meta = ScoreMetadata(
                    name='restraint_dist',
                    title='Restraint Satisfaction (Å)',
                    guide=1.0, lower=0.0, upper='95%', order=2,
            )
            record['restraint_dist'] = np.max(restraint_distances)
            metadata[meta.name] = meta

        if len(residue_specific_restraint_distances) > 1:
            for i in residue_specific_restraint_distances:
                res = '{0}{1}'.format(sequence_map[i], i)
                key = 'restraint_dist_{0}'.format(res.lower())
                meta = ScoreMetadata(
                        name=key,
                        title='Restraint Satisfaction for {0} (Å)'.format(res),
                        guide=1.0, lower=0.0, upper='95%', order=3,
                )
                record[key] = np.max(residue_specific_restraint_distances[i])
                metadata[meta.name] = meta

        records.append(record)

    if pdb_paths:
        sys.stdout.write('\n')

    return records, metadata

def parse_restraints(path):
    restraints = []
    parsers = {
            'CoordinateConstraint': CoordinateRestraint,
            'AtomPairConstraint': AtomPairRestraint,
            'AtomPair': AtomPairRestraint,
            'Dihedral': DihedralRestraint,
    }

    with open(path) as file:
        for line in file:
            if not line.strip(): continue
            if line.startswith('#'): continue

            tokens = line.split()
            type, args = tokens[0], tokens[1:]

            if type not in parsers:
                raise IOError("Cannot parse '{0}' restraints.".format(type))

            restraint = parsers[type](args)
            restraints.append(restraint)

    return restraints

def parse_filter(desc, default_order=None):
    """
    Parse a filter name to get information about how to interpret and display 
    that filter.  For example, consider the following filter name:

        "Foldability Filter [+|guide 0.1]"

    Everything outside the brackets is the name of the filter.  This is 
    converted into a simpler name which can be referred to later on by making 
    everything lower case, dropping anything inside of parentheses, replacing 
    non-ASCII characters with ASCII one (on a best-effort basis, some letters 
    may be dropped), and replacing spaces and dashes with underscores (expect 
    trailing spaces, which are removed).

    Everything in the brackets provides metadata about the filter.  All 
    metadata is optional.  Different pieces of metadata are separated by 
    vertical bars, and do not have to be labeled.  If unlabeled, the metadata 
    are interpreted in the following order:

    1. Direction (i.e. '+' or '-', are higher or lower values better?)
    2. Order (i.e. how to sort a list of filters?)
    3. Guide (i.e. where should a dashed line be drawn in the GUI?)
    4. Lower limit (i.e. the default lower limit in the GUI)
    5. Upper limit (i.e. the default upper limit in the GUI)

    If labeled, the data can appear in any order.  The labels corresponding to 
    the above arguments are abbreviated as follows: 'dir', 'order', 'guide', 
    'lower', 'upper'.  No unlabeled metadata can appear after any labeled 
    metadata.
    """
    meta = re.search(r'\[\[?(.*?)\]\]?', desc)

    if not meta:
        return ScoreMetadata(desc)

    args = {}
    if default_order is not None:
        args['order'] = default_order

    title = desc[:meta.start()] + desc[meta.end():]
    tokens = meta.group(1).split('|')
    default_keys = 'dir', 'order', 'guide', 'min', 'max'
    default_ok = True

    for i, token in enumerate(tokens):
        try:
            key, value = token.strip().split(None, 1)
            # Stop using the defaults once we've been given an explicit key.
            default_ok = False
        except ValueError:
            if default_ok and i < len(default_keys):
                key, value = default_keys[i], token
            else:
                raise IOError("Unknown key for '{0}' in filter '{1}'".format(token, desc))

        args[key] = value

    return ScoreMetadata(title, **args)

def name_from_title(title):
    from unicodedata import normalize

    # Replace any whitespace with an underscore.
    name = re.sub(r'[ _-]+', '_', title)

    # Try to replace unicode characters with alphanumeric ASCII ones.
    name = normalize('NFKD', unicode(name)).encode('ascii', 'ignore')
    name = ''.join(x for x in name if x.isalnum() or x in '_')
    name = name.strip('_')

    # Make everything lower case.
    name = name.lower()

    return name

def xyz_to_array(xyz):
    """
    Convert a list of strings representing a 3D coordinate to floats and return
    the coordinate as a ``numpy`` array.
    """
    return np.array([float(x) for x in xyz])

def angle(array_of_xyzs):
    """
    Calculates angle between three coordinate points (I could not find a package
    that does this but if one exists that would probably be better). Used for Angle constraints. 
    """
    ab = array_of_xyzs[0] - array_of_xyzs[1]
    cb = array_of_xyzs[2] - array_of_xyzs[1]
    return np.arccos((np.dot(ab,cb)) / (np.sqrt(ab[0]**2 + ab[1]**2  \ 
        + ab[2]**2) * np.sqrt(cb[0]**2 + cb[1]**2 + cb[2]**2)))

def dihedral(array_of_xyzs):
    """
    Calculates dihedral angle between four coordinate points. Used for
    dihedral constraints. 
    """
    p1 = array_of_xyzs[0]
    p2 = array_of_xyzs[1]
    p3 = array_of_xyzs[2]
    p4 = array_of_xyzs[3]

    vector1 = -1.0 * (p2 - p1)
    vector2 = p3 - p2
    vector3 = p4 - p3

    # Normalize vector so as not to influence magnitude of vector
    # rejections
    vector2 /= np.linalg.norm(vector2)

    # Vector rejections:
    # v = projection of vector1 onto plane perpendicular to vector2
    #   = vector1 - component that aligns with vector2
    # w = projection of vector3 onto plane perpendicular to vector2
    #   = vector3 = component that aligns with vector2
    v = vector1 - np.dot(vector1, vector2) * vector2
    w = vector3 - np.dot(vector3, vector2) * vector2

    # Angle between v and w in a plane that is the torsion angle
    # v and w not normalized explicitly, but we use tan so that doesn't
    # matter
    x = np.dot(v, w)
    y = np.dot(np.cross(vector2, v), w)
    principal_dihedral = np.arctan2(y,x)
    # I'm leaving this variable explicit because it should be clear that
    # we need to make sure there are no non-principle angles that better
    # satisfy the constraint for some reason, but that needs to be done
    # outside this function. 
    return principle_dihedral

def find_pareto_front(metrics, metadata, columns, depth=1, epsilon=1e-7, progress=None):
    """
    Return the subset of the given metrics that are Pareto optimal with respect 
    to the given columns.

    Arguments
    =========
    metrics: DataFrame
        A dataframe where each row is a different model or design and each 
        column is a different score metric.

    metadata: dict
        Extra information about each score metric, in particular whether or not 
        bigger values are considered better or worse.  You can get this data 
        structure from structures.load().

    columns: list
        The score metrics to consider when calculating the Pareto front.

    depth: int
        The number of Pareto fronts to return.  In other words, if depth=2, the 
        Pareto front will be calculated, then those points (and any within 
        epsilon of them) will be set aside, then the Pareto front of the 
        remaining points will be calculated, then the union of both fronts will 
        be returned.

    epsilon: float
        How close two points can be (in all the dimensions considered) before 
        they are considered the same and one is excluded from the Pareto front 
        (even if it is non-dominated).  This is roughly in units of percent of 
        the range of the points.

    progress: func
        A function that will be called in the innermost loop as follows:
        `progress(curr_depth, tot_depth, curr_hit, tot_hits)`.  This is 
        primarily intended to allow the caller to present a progress bar, since 
        increasing the depth can dramatically increase the amount of time this 
        function takes.

    Returns
    =======
    front: DataFrame
        The subset of the given metrics that is Pareto optimal with respect to 
        the given score metrics.

    There are several ways to tune the number of models that are returned by 
    this function.  These are important to know, because this function is used 
    to filter models between rounds of design, and there are always practical 
    constraints on the number of models that can be carried on:

    - Columns: This is only mentioned for completeness, because you should pick 
      your score metrics based on which scores you think are informative, not 
      based on how many models you need.  But increasing the number of score 
      metrics increases the number of models that are selected, sometimes 
      dramatically.

    - Depth: Increasing the depth increases the number of models that are 
      selected by including models that are just slightly behind the Pareto 
      front.

    - Epsilon: Increasing the epsilon decreases the number of models that are 
      selected by discarding the models in the Pareto front that are too 
      similar to each other.
      
    In short, tune depth to get more models and epsilon to get fewer.  You 
    can also tune both at once to get a large but diverse set of models.
    """
    import pareto

    indices_from_cols = lambda xs: [metrics.columns.get_loc(x) for x in xs]
    percentile = lambda x, q: metrics[x].quantile(q/100)
    epsilons_from_cols = lambda xs: [
            epsilon * abs(percentile(x, 90) - percentile(x, 10)) / (90 - 10)
            for x in xs]

    epsilons = epsilons_from_cols(columns)
    maximize = [x for x in columns if metadata[x].direction == '+']
    maximize_indices = indices_from_cols(maximize)
    column_indices = indices_from_cols(columns)

    def boxify(df): #
        boxed_df = pd.DataFrame()
        for col, eps in zip(columns, epsilons):
            boxed_df[col] = np.floor(df[col] / eps)
        return boxed_df

    mask = np.zeros(len(metrics), dtype='bool')
    too_close = np.zeros(len(metrics), dtype='bool')
    all_boxes = boxify(metrics)
    labeled_metrics = metrics.copy()
    labeled_metrics['_pip_index'] = metrics.index
    id = labeled_metrics.columns.get_loc('_pip_index')

    for i in range(depth):
        # Figure out which points are within epsilon of points that are already 
        # in the front, so they can be excluded from the search.  Without this, 
        # points that are rejected for being too similar at one depth will be 
        # included in the next depth.
        front_boxes = boxify(metrics[mask])
        for j, (_, row) in enumerate(front_boxes.iterrows()):
            if progress: progress(i+1, depth, j+1, len(front_boxes))
            too_close |= all_boxes.apply(
                    lambda x: (x == row).all(), axis='columns')

        candidates = [labeled_metrics[too_close == False]]
        front = pareto.eps_sort(
                candidates, column_indices, epsilons, maximize=maximize_indices)

        for row in front:
            assert not mask[row[id]]
            mask[row[id]] = True

    return metrics[mask]


class ScoreMetadata(object):

    def __init__(self, title, dir='-', guide=None, lower=None, upper=None, order=None, name=None):
        self.title = title
        self.name = name or name_from_title(title)
        self.order = order
        self.direction = dir
        self.guide = guide and float(guide)
        self.lower = lower
        self.upper = upper

        def cutoff(limit, x, default):
            if limit is None:
                return default

            if isinstance(limit, (str, unicode)):
                if limit.endswith('%'):
                    value = float(limit[:-1])
                    return np.percentile(x, value)
                else:
                    return float(value)

            else:
                return limit


        self.limits = lambda x: (
                cutoff(lower, x, min(x)),
                cutoff(upper, x, max(x)),
        )

    def __repr__(self):
        return '<ScoreMetadata name="{0}">'.format(self.name)

    def to_dict(self):
        d = {}
        d['title'] = self.title
        d['name'] = self.name
        d['dir'] = self.direction

        if self.guide:
            d['guide'] = self.guide
        if self.lower:
            d['lower'] = self.lower
        if self.upper:
            d['upper'] = self.upper
        if self.order:
            d['order'] = self.order

        return d


class CoordinateRestraint(object):

    def __init__(self, args):
        self.atom_name = args[0]
        self.residue_id = int(args[1])
        self.residue_ids = [self.residue_id]
        self.atom = self.atom_name, self.residue_id
        self.coord = xyz_to_array(args[4:7])

    def distance_from_ideal(self, atom_xyzs):
        return euclidean(self.coord, atom_xyzs[self.atom])


class AtomPairRestraint(object):

    def __init__(self, args):
        self.atom_names = [args[0], args[2]]
        self.residue_ids = [int(args[i]) for i in (1,3)]
        self.atom_pair = zip(self.atom_names, self.residue_ids)
        self.ideal_distance = float(args[5])

    def distance_from_ideal(self, atom_xyzs):
        coords = [atom_xyzs[x] for x in self.atom_pair]
        return euclidean(*coords) - self.ideal_distance

class DihedralRestraint(object):

    def __init__(self, args):
        self.atom_names = [args[0],args[2],args[4],args[6]]
        self.residue_ids = [int(args[i]) for i in (1,3,5,7)]
        self.atoms = zip(self.atom_names, self.residue_ids)
        self.ideal_dihedral = float(args[9])

    def distance_from_ideal(self, atom_xyzs):
        coords = [atom_xyzs[x] for x in self.atom_pair]

class AngleRestraint(object):

    def __init__(self, args):
        self.atom_names = [args[0],args[2],args[4],args[6]]
        self.residue_ids = [int(args[i]) for i in (1,3,5,7)]
        self.atoms = zip(self.atom_names, self.residue_ids)
        self.ideal_angle = float(args[9])

    def distance_from_ideal(self, atom_xyzs):
        coords = [atom_xyzs[x] for x in self.atom_pair]


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
        self.representative = self.rep = self.scores.idxmin()

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
