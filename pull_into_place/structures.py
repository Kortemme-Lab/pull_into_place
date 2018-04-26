#!/usr/bin/env python2
# encoding: utf-8

from __future__ import division
from __future__ import unicode_literals

"""\
This module provides a function that will read a directory of PDB files and
return a pandas data frame containing a number of score, distance, and sequence
metrics for each structure.  This information is also cached, because it takes
a while to calculate up front.  Note that the cache files are pickles and seem
to depend very closely on the version of pandas used to generate them.  For
example, caches generated with pandas 0.15 can't be read by pandas 0.14.
"""

import sys, os, re, glob, collections, gzip, re, yaml, codecs
import numpy as np, scipy as sp, pandas as pd
from scipy.spatial.distance import euclidean
from klab import scripting
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

    cached_records = []
    uncached_paths = pdb_paths
    metadata = {}

    if use_cache:
        try:
            cached_records = pd.read_pickle(cache_path).to_dict('records')
            cached_paths = set(x['path'] for x in cached_records)
            uncached_paths = [
                    pdb_path for pdb_path in pdb_paths
                    if os.path.basename(pdb_path) not in cached_paths]

            with codecs.open(metadata_path, encoding='utf8') as file:
                metadata_list = [ScoreMetadata(**x) for x in yaml.safe_load(file)]
                metadata = {x.name: x for x in metadata_list}

        except:
            cached_records = []
            uncached_paths = pdb_paths
            metadata = {}

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
    with codecs.open(metadata_path, 'w', encoding='utf8') as file:
        yaml.safe_dump([v.to_dict() for k,v in metadata.items()], file)

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
    fragment_size = 0

    # It's kinda hard to tell which lines are part of the score table.  The 
    # first column has some pretty heterogeneous strings (examples below) and 
    # all the other columns are just numbers.  My strategy here is to try to 
    # make a regular expression that matches all of these examples, with the 
    # exception of the ligand.  I think the ligand will simply be too 
    # heterogeneous to match, and the purpose of this is to get dunbrack 
    # scores, which the ligand doesn't have.
    #
    #   MET:NtermProteinFull_1
    #   ASN_2
    #   LYS:protein_cutpoint_lower_39
    #   ASP:protein_cutpoint_upper_40
    #   ALA:CtermProteinFull_124
    #   HIS_D_224
    #   pdb_EQU_250

    score_table_pattern = re.compile(
            r'^[A-Z]{3}(?:_[A-Z])?'  # Residue name with optional tautomer.
            r'(?::[A-Za-z_]+)?'      # Optional patch type.
            r'_([0-9]+) '            # Residue number preceded by underscore.
    )                                # The terminal space is important to match
                                     # the full residue number.

    for i, path in enumerate(sorted(pdb_paths)):
        record = {'path': os.path.basename(path)}
        sequence = ""
        sequence_map = {}
        last_residue_id = None
        dunbrack_index = None
        dunbrack_scores = {}

        # Update the user on our progress, because this is often slow.

        sys.stdout.write("\rReading '{}' [{}/{}]".format(
            os.path.relpath(os.path.dirname(path)), i+1, len(pdb_paths)))
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
            line = line.decode('utf8')

            score_table_match = \
                    dunbrack_index and score_table_pattern.match(line)

            if line.startswith('pose'):
                meta = ScoreMetadata(
                        name='total_score',
                        title='Total Score',
                        unit='REU',
                        order=1,
                )
                record['total_score'] = float(line.split()[1])
                metadata[meta.name] = meta

            elif line.startswith('label'):
                fields = line.split()
                dunbrack_index = fields.index('fa_dun')

            elif score_table_match:
                residue_id = int(score_table_match.group(1))
                for restraint in restraints:
                    if residue_id in restraint.residue_ids:
                        dunbrack_score = float(line.split()[dunbrack_index])
                        dunbrack_scores[residue_id] = dunbrack_score
                        break

            elif line.startswith('rmsd'):
                meta = ScoreMetadata(
                        name='loop_rmsd',
                        title='Loop RMSD (Backbone Heavy-Atom)',
                        unit='Å',
                        guide=1.0, lower=0.0, upper='95%', order=4,
                )
                record[meta.name] = float(line.split()[1])
                metadata[meta.name] = meta

            elif line.startswith('  all_heavy_atom_unsats'):
                meta = ScoreMetadata(
                        name='buried_unsats',
                        title='Buried Unsatsified H-Bonds',
                        order=5,
                )
                record[meta.name] = float(line.split()[2])
                metadata[meta.name] = meta

            elif line.startswith('  sc_heavy_atom_unsats'):
                meta = ScoreMetadata(
                        name='buried_unsats_sidechain',
                        title='Buried Unsatisfied H-Bonds (Sidechain)',
                        order=5,
                )
                record[meta.name] = float(line.split()[2])
                metadata[meta.name] = meta

            elif line.startswith('  bb_heavy_atom_unsats'):
                meta = ScoreMetadata(
                        name='buried_unsats_backbone',
                        title='Buried Unsatisfied H-Bonds (Backbone)',
                        order=5,
                )
                record[meta.name] = float(line.split()[2])
                metadata[meta.name] = meta

            elif line.startswith('time'):
                meta = ScoreMetadata(
                        name='simulation_time',
                        title='Simulation Time',
                        unit='sec',
                        order=5,
                )
                record[meta.name] = float(line.split()[1])
                metadata[meta.name] = meta

            elif line.startswith('FragmentScoreFilter '):
                fragment_size = line.split()[2].split('-')[0]

            elif line.startswith('FSF') or line.startswith('FragmentScoreFilter_metric'):
                splitline = line.split()
                if splitline[1] == 'Max':
                    max_res = 0
                    max_crmsd = 0
                    if splitline[3] == 'res:':
                        max_res = splitline[3]
                        meta = ScoreMetadata(
                                name='max_fragment_crmsd_position',
                                title = 'Max {}-Residue Fragment RMSD \
(C-Alpha) Position'.format(fragment_size),
                                order=7)
                    elif splitline[3] == 'score:':
                        max_crmsd = splitline[3]
                        meta = ScoreMetadata(
                                name='max_fragment_crmsd_score',
                                title = 'Max {}-Residue Fragment RMSD \
(C-Alpha)'.format(fragment_size),
                                order=7)

                elif splitline[1] == 'Min':
                    min_res = 0
                    min_crmsd = 0
                    if splitline[3] == 'res:':
                        min_res = splitline[3]
                        meta = ScoreMetadata(
                                name='min_fragment_crmsd_position',
                                title = 'Min {}-Residue Fragment RMSD \
(C-Alpha) Position'.format(fragment_size),
                                order=8)
                    elif splitline[3] == 'score:':
                        min_crmsd = splitline[3]
                        meta = ScoreMetadata(
                                name='min_fragment_crmsd_score',
                                title = 'Min {}-Residue Fragment RMSD \
(C-Alpha)'.format(fragment_size),
                                order=8)

                elif splitline[1] == 'Avg':
                    meta = ScoreMetadata(
                            name='avg_fragment_crmsd',
                            title='Avg {}-Residue Fragment RMSD \
(C-Alpha)'.format(fragment_size),
                            order=9)
                else:
                    position = splitline[2]
                    crmsd = splitline[4]
                    meta = ScoreMetadata(
                            name='fragment_crmsd_pos_{}'.format(position),
                            title='{}-Residue Fragment RMSD at Res {} \
(C-Alpha)'.format(fragment_size,position),
                            order=6)

                record[meta.name] = float(splitline[4])
                metadata[meta.name] = meta

            elif line.startswith('EXTRA_SCORE'):
                tokens = line[len('EXTRA_SCORE_'):].rsplit(None, 1)
                meta = parse_extra_metric(tokens[0], 5)
                record[meta.name] = float(tokens[1])
                metadata[meta.name] = meta

            elif line.startswith('EXTRA_METRIC'):
                tokens = line[len('EXTRA_METRIC '):].rsplit(None, 1)

                # Ignore the BuriedUnsat filter.  It just reports 911 every 
                # time, and we extract the actual buried unsat information from 
                # some other lines it adds to the PDB.
                if tokens[0] == 'IGNORE':
                    continue
                if tokens[0] == 'Buried Unsatisfied H-Bonds [-|#]':
                    continue

                meta = parse_extra_metric(tokens[0], 5)
                record[meta.name] = float(tokens[1])
                metadata[meta.name] = meta

            elif (line.startswith('ATOM') or line.startswith('HETATM')):
                atom_name = line[12:16].strip()
                residue_id = int(line[22:26].strip())
                residue_name = line[17:20].strip()

                # Keep track of this model's sequence.

                if residue_id != last_residue_id:
                    if line.startswith('ATOM'): 
                        one_letter_code = residue_type_3to1_map.get(residue_name, 'X')
                        sequence += one_letter_code
                        sequence_map[residue_id] = one_letter_code
                        last_residue_id = residue_id
                    elif line.startswith('HETATM'):
                        sequence_map[residue_id] = 'X'
                        last_residue_id = residue_id

                # Save the coordinate for this atom.  This will be used later 
                # to calculate restraint distances.

                atom_xyzs[atom_name, residue_id] = xyz_to_array((
                        line[30:38], line[38:46], line[46:54]))

        # Calculate how well each restraint was satisfied.

        restraint_values = {}
        restraint_values_by_residue = {}
        is_sidechain_restraint = {}
        restraint_units = {
                'dist': 'Å',
                'angle': '°',
        }

        for restraint in restraints:
            d = restraint.distance_from_ideal(atom_xyzs)
            metric = restraint.metric
            backbone_atoms = set(['N', 'C', 'CA', 'O'])
            backbone_restraint = backbone_atoms.issuperset(restraint.atom_names)

            restraint_values.setdefault(metric, []).append(d)
            restraint_values_by_residue.setdefault(metric, {})
            for i in restraint.residue_ids:
                restraint_values_by_residue[metric].setdefault(i, []).append(d)
                is_sidechain_restraint[i] = (not backbone_restraint) \
                        or is_sidechain_restraint.get(i, False)

        for metric, values in restraint_values.items():
            meta = ScoreMetadata(
                    name='restraint_{0}'.format(metric),
                    title='Restraint Satisfaction',
                    unit=restraint_units[metric],
                    guide=1.0, lower=0.0, upper='95%', order=2,
            )
            record[meta.name] = np.max(values)
            metadata[meta.name] = meta

        for metric, values_by_residue in restraint_values_by_residue.items():
            if len(values_by_residue) <= 1:
                continue

            for i in values_by_residue:
                # I want to put the amino acid in these names, because I think 
                # it looks nice, but it causes problems for positions that can 
                # mutate.  So I assume that if a position has a sidechain 
                # restraint, it must not be allowed to mutate.
                aa = sequence_map[i] if is_sidechain_restraint[i] else 'X'
                res = '{0}{1}'.format(aa, i)
                meta = ScoreMetadata(
                        name='restraint_{0}_{1}'.format(metric, res.lower()),
                        title='Restraint Satisfaction for {0}'.format(res),
                        unit=restraint_units[metric],
                        guide=1.0, lower=0.0, upper='95%', order=3,
                )
                record[meta.name] = np.max(values_by_residue[i])
                metadata[meta.name] = meta

        # Finish calculating some records that depend on the whole structure.

        record['sequence'] = sequence
        for i, score in dunbrack_scores.items():
            aa = sequence_map[i] if is_sidechain_restraint[i] else 'X'
            res = '{0}{1}'.format(aa, i)
            meta = ScoreMetadata(
                    name='dunbrack_score_{0}'.format(res.lower()),
                    title='Dunbrack Score for {0}'.format(res),
                    unit='REU',
                    order=5,
            )
            record[meta.name] = score
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
            'NamedAngle': AngleRestraint,
    }

    with open(path) as file:
        for line in file:
            if not line.strip(): continue
            if line.startswith('#'): continue

            tokens = line.split()
            key, args = tokens[0], tokens[1:]

            if key not in parsers:
                raise IOError("Cannot parse '{0}' restraints.".format(key))

            restraint = parsers[key](args)
            restraints.append(restraint)

    return restraints

def parse_extra_metric(desc, default_order=None):
    """
    Parse a filter name to get information about how to interpret and display 
    that filter.  For example, consider the following filter name:

        "Foldability Filter [+|guide 0.1]"

    Everything outside the brackets is the name of the filter.  This is 
    converted into a simpler name which can be referred to later on by making 
    everything lower case, dropping anything inside of parentheses, replacing 
    non-ASCII characters with ASCII ones (on a best-effort basis, some letters 
    may be dropped), and replacing spaces and dashes with underscores (expect 
    trailing spaces, which are removed).

    Everything in the brackets provides metadata about the filter.  All 
    metadata is optional.  Different pieces of metadata are separated by 
    vertical bars, and do not have to be labeled.  If unlabeled, the metadata 
    are interpreted in the following order:

    1. Direction (i.e. '+' or '-', are higher or lower values better?)
    2. Unit (i.e. how to label the metric?)
    3. Order (i.e. how to sort a list of filters?)
    4. Guide (i.e. where should a dashed line be drawn in the GUI?)
    5. Lower limit (i.e. the default lower limit in the GUI)
    6. Upper limit (i.e. the default upper limit in the GUI)

    If labeled, the data can appear in any order.  The labels corresponding to 
    the above arguments are abbreviated as follows: 'dir', 'unit', 'order', 
    'guide', 'lower', 'upper'.  No unlabeled metadata can appear after any 
    labeled metadata.
    """
    meta = re.search(r'\[\[?(.*?)\]\]?', desc)

    if not meta:
        return ScoreMetadata(desc, order=default_order)

    args = {}
    if default_order is not None:
        args['order'] = default_order

    title = desc[:meta.start()] + desc[meta.end():]
    tokens = meta.group(1).split('|')
    default_keys = 'dir', 'unit', 'order', 'guide', 'min', 'max'
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
    name = normalize('NFKD', name).encode('ascii', 'ignore')

    # Remove any remaining characters that aren't alphanumeric or underscore.
    name = ''.join(x for x in name if x.isalnum() or x in '_')

    # Remove trailing underscores.
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
    principle_dihedral = np.arctan2(y,x)
    # I'm leaving this variable explicit because it should be clear that
    # we need to make sure there are no non-principle angles that better
    # satisfy the constraint for some reason, but that needs to be done
    # outside this function. 
    return principle_dihedral


def make_picks(workspace, pick_file=None, clear=False, use_cache=True, dry_run=False, keep_dups=False):
    """
    Return a subset of the designs in the given data frame based on the 
    conditions specified in the given "pick" file.

    An example pick file is show below::

        threshold:
        - restraint_dist < 1
        - buried_unsatisfied_h_bonds < 1

        pareto:
        - total_score
        - restraint_dist
        - foldability

        depth: 1
        epsilon: 0.5%

    Any designs not meeting the conditions set in the "threshold" section will 
    be discarded.  Any designs that are non-dominated with respect to the 
    metrics listed in the "Pareto" section will be kept.  The "depth" and 
    "epsilon" parameters provide a measure of control over how many designs 
    are included in the Pareto front.
    """
    # Read the rules for making picks from the given file.

    if pick_file is None:
        pick_file = workspace.pick_file

    if not os.path.exists(pick_file):
        raise IOError("""\
Could not find '{}'.

Either specify a pick file on the command line, or create a file called 
`pick.yml` and put in a directory in your workspace that corresponds to the 
step you want it to apply to.""")

    import yaml
    with open(pick_file) as file:
        rules = yaml.load(file)

    print "Picking designs according to '{0}'.".format(os.path.relpath(pick_file))
    print

    pareto = rules.get('pareto', [])
    thresholds = rules.get('threshold', [])

    known_keys = 'threshold', 'pareto', 'depth', 'epsilon'
    unknown_keys = set(rules) - set(known_keys)

    if unknown_keys:
        not_understood = '\n'.join('    ' + x for x in sorted(unknown_keys))
        did_you_mean = '\n'.join('    ' + x for x in known_keys)
        raise IOError("""\
The following parameters in '{2}' are not understood:
{0}

Did you mean:
{1}\n""".format(not_understood, did_you_mean, os.path.relpath(pick_file)))

    # Load all the metrics for the models we're picking from.

    if clear:
        workspace.clear_inputs()

    predecessor = workspace.predecessor
    metrics = []
    metadata = {}

    for input_dir in predecessor.output_subdirs:
        submetrics, submetadata = load(
                input_dir,
                use_cache=use_cache,
        )
        submetrics['abspath'] = submetrics.apply(
                lambda row: os.path.abspath(os.path.join(input_dir, row['path'])),
                axis='columns',
        )
        metrics.append(submetrics)
        metadata.update(submetadata)

    metrics = pd.concat(metrics, ignore_index=True)

    # Check to make sure we know about all the metrics we were given, and 
    # produce a helpful error if we find something unexpected (e.g. maybe a 
    # typo?).  This is a little complicated for the threshold queries, because 
    # running them is the only way to find out if they have any problems.

    unknown_metrics = set(pareto) - set(metadata)

    for query in thresholds:
        try:
            metrics.query(query)
        except pd.core.computation.ops.UndefinedVariableError as err:
            # Kinda gross, but we have to parse the error message to get the 
            # name of the metric causing the problem.
            unknown_metric = re.search("'(.+)'", str(err)).group(1)
            unknown_metrics.add(unknown_metric)

    if unknown_metrics:
        not_understood = '\n'.join('    ' + x for x in sorted(unknown_metrics))
        did_you_mean = '\n'.join('    ' + x for x in sorted(metadata))
        raise IOError("""\
The following metrics are not understood:
{0}

Did you mean:
{1}\n""".format(not_understood, did_you_mean))

    # Tell the user whether high or low values are favored for each metric 
    # included in the Pareto front, so they can confirm that we're doing the 
    # right thing.
    
    if pareto:
        print """\
Please confirm whether high (+) or low (-) values should be preferred for each 
of the following metrics:"""

        for metric in rules['pareto']:
            print "  ({dir}) {metric}".format(
                    metric=metric,
                    dir=metadata[metric].direction)

        print
        print """\
If there's an error, it's probably because you didn't specify a direction in 
the name of the filter, e.g. "Foldability [+]".  To avoid this problem in the 
future, add the appropriate direction (in square brackets) to the filter name 
in 'filters.xml'.  To fix the immediate problem, go into the directory 
containing your design PDBs, manually edit the file called 'metrics.yml', and 
correct the 'dir' field for any metrics necessary."""
        print

    # Figure out how long the longest status message will be, so we can get our 
    # output to line up nicely.

    class StatusBar:
        update_line = "  {0}:"

        def __init__(self):
            self.w1 = 30

        def init(self, df):
            self.n = len(df)
            self.w2 = len(str(self.n))
            return "{message:<{w1}} {n:>{w2}}".format(
                    message="Total number of designs",
                    n=self.n, w1=self.w1, w2=self.w2)

        def update(self, df, status):
            dn = len(df) - self.n
            self.n = len(df)
            return "{message:<{w1}} {n:>{w2}} {dn:>{w3}}".format(
                    message=self.update_line.format(status),
                    n=self.n, dn='(-{})'.format(abs(dn)),
                    w1=self.w1, w2=self.w2, w3=self.w2+3)

        def adjust_width(self, status):
            self.w1 = max(self.w1, len(self.update_line.format(status)))



    status = StatusBar()
    for query in thresholds:
        status.adjust_width(repr(query))

    print status.init(metrics)

    # Ignore any designs that are missing data.

    metrics.dropna(inplace=True)
    print status.update(metrics, "minus missing data")

    # Keep only the lowest scoring model for each set of identical sequences.

    if not keep_dups:
        groups = metrics.groupby('sequence', group_keys=False)
        metrics = groups.\
                apply(lambda df: df.ix[df.total_score.idxmin()]).\
                reset_index(drop=True)
        print status.update(metrics, 'minus duplicate sequences')

    # Remove designs that don't pass the given thresholds.

    for query in thresholds:
        metrics = metrics.query(query)
        print status.update(metrics, repr(query))

    # Remove designs that aren't in the Pareto front.

    if pareto:
        def progress(i, depth, j, front): #
            sys.stdout.write('\x1b[2K\r  minus Pareto dominated:    calculating... [{}/{}] [{}/{}]'.format(i, depth, j, front))
            if i == depth and j == front:
                sys.stdout.write('\x1b[2K\r')
            sys.stdout.flush()

        metrics = find_pareto_front(
                metrics, metadata, pareto,
                depth=rules.get('depth', 1),
                epsilon=rules.get('epsilon'),
                progress=progress,
        )
        print status.update(metrics, 'minus Pareto dominated')

    # Remove designs that have already been picked.

    existing_inputs = set(
            os.path.abspath(os.path.realpath(x))
            for x in workspace.input_paths)
    metrics = metrics.query('abspath not in @existing_inputs')
    print status.update(metrics, 'minus current inputs')

    # Symlink the picked designs into the input directory of the next round.

    if not dry_run:
        existing_ids = set(
                int(x[0:-len('.pdb.gz')])
                for x in os.listdir(workspace.input_dir)
                if x.endswith('.pdb.gz'))
        next_id = max(existing_ids) + 1 if existing_ids else 0

        for id, picked_index in enumerate(metrics.index, next_id):
            target = metrics.loc[picked_index]['abspath']
            link_name = os.path.join(workspace.input_dir, '{0:04}.pdb.gz')
            scripting.relative_symlink(target, link_name.format(id))

    print
    print "Picked {} designs.".format(len(metrics))

    if dry_run:
        print "(Dry run: no symlinks created.)"

def find_pareto_front(metrics, metadata, columns, depth=1, epsilon=None, progress=None):
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
        the range of the points.  By default this is small enough that you can 
        basically assume that no two points will be considered the same.

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

    # Bail out if the data frame is empty, because otherwise the Pareto front 
    # calculation will choke on something.
    if len(metrics) == 0:
        return metrics

    # https://github.com/matthewjwoodruff/pareto.py
    import pareto

    indices_from_cols = lambda xs: [metrics.columns.get_loc(x) for x in xs]
    percentile = lambda x, q: metrics[x].quantile(q/100)
    epsilons = [
            (epsilon or 1e-7) * abs(percentile(x, 90) - percentile(x, 10)) / (90 - 10)
            for x in columns
    ]
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
    labeled_metrics['_pip_index'] = range(len(metrics))
    id = labeled_metrics.columns.get_loc('_pip_index')

    for i in range(depth):
        # Figure out which points are within epsilon of points that are already 
        # in the front, so they can be excluded from the search.  Without this, 
        # points that are rejected for being too similar at one depth will be 
        # included in the next depth.
        # 
        # This check is unfortunately very expensive, so we skip it for the 
        # default value of epsilon, which is so small (1e-7) that we assume no 
        # points will be rejected for being too similar.

        if epsilon is None:
            candidates = [labeled_metrics[~mask]]
        else:
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

    def __init__(self, title, dir='-', unit=None, guide=None, lower=None, upper=None, order=None, fmt=None, name=None):
        title = title.strip()
        self.raw_title = title
        self.title = '{0} ({1})'.format(title, unit) if unit else title
        self.unit = unit
        self.name = name or name_from_title(title)
        self.order = order
        self.direction = dir
        self.guide = guide and float(guide)
        self.lower = lower
        self.upper = upper
        self.format = fmt

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
        d['title'] = self.raw_title
        d['name'] = self.name
        d['dir'] = self.direction

        if self.unit:
            d['unit'] = self.unit
        if self.guide:
            d['guide'] = self.guide
        if self.lower:
            d['lower'] = self.lower
        if self.upper:
            d['upper'] = self.upper
        if self.order:
            d['order'] = self.order
        if self.format:
            d['fmt'] = self.format

        return d


class CoordinateRestraint(object):

    def __init__(self, args):
        self.metric = 'dist'
        self.atom_name = args[0]
        self.atom_names = [args[0]]
        self.residue_id = int(args[1])
        self.residue_ids = [self.residue_id]
        self.atom = self.atom_name, self.residue_id
        self.coord = xyz_to_array(args[4:7])

    def distance_from_ideal(self, atom_xyzs):
        return euclidean(self.coord, atom_xyzs[self.atom])


class AtomPairRestraint(object):

    def __init__(self, args):
        self.metric = 'dist'
        self.atom_names = [args[0], args[2]]
        self.residue_ids = [int(args[i]) for i in (1,3)]
        self.atom_pair = zip(self.atom_names, self.residue_ids)
        self.ideal_distance = float(args[5])

    def distance_from_ideal(self, atom_xyzs):
        coords = [atom_xyzs[x] for x in self.atom_pair]
        return euclidean(*coords) - self.ideal_distance


class DihedralRestraint(object):

    def __init__(self, args):
        self.metric = 'angle'
        self.atom_names = [args[0], args[2], args[4], args[6]]
        self.residue_ids = [int(args[i]) for i in (1,3,5,7)]
        self.atoms = zip(self.atom_names, self.residue_ids)
        self.ideal_dihedral = float(args[9]) * (360 / (2 * np.pi))

    def distance_from_ideal(self, atom_xyzs):
        coords = [atom_xyzs[x] for x in self.atoms]
        measured_dihedral = dihedral(coords) * (360 / (2 * np.pi))
        # Make sure we don't get the wrong number because of
        # non-principle angles:
        dihedrals = [abs(measured_dihedral - self.ideal_dihedral), abs(measured_dihedral + \
                    (360) - self.ideal_dihedral), abs(measured_dihedral - (360) - \
                    self.ideal_dihedral)]
        return min(dihedrals) 


class AngleRestraint(object):

    def __init__(self, args):
        self.metric = 'angle'
        self.atom_names = [args[0], args[2], args[4], args[6]]
        self.residue_ids = [int(args[i]) for i in (1,3,5)]
        self.atoms = zip(self.atom_names, self.residue_ids)
        self.ideal_angle = float(args[7]) * (360 / (2 * np.pi))

    def distance_from_ideal(self, atom_xyzs):
        coords = [atom_xyzs[x] for x in self.atoms]
        measured_angle = angle(coords) * (360 / (2 * np.pi))
        # Make sure we don't get the wrong number because of
        # non-principle angles:
        angles = [abs(measured_angle - self.ideal_angle), abs(measured_angle + (360) -
                self.ideal_angle), abs(measured_angle - (360) - self.ideal_angle)]
        return min(angles)


class Design (object):
    """
    Represent a single validated design.  Each design is associated with 500
    scores, 500 restraint distances, and a "representative" (i.e. lowest
    scoring) model.  The representative has its own score and restraint
    distance, plus a path to a PDB structure.
    """

    def __init__(self, directory):
        self.directory = directory
        self.structures, self.metadata = load(directory)
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
