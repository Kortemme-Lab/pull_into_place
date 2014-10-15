#!/usr/bin/env python2

import sys, os, glob, collections, gzip
import numpy as np, scipy as sp, pandas as pd
from . import workspaces

def load(pdb_dir, use_cache=True):
    workspace = workspaces.from_directory(pdb_dir)
    pdb_paths = glob.glob(os.path.join(pdb_dir, '*.pdb.gz'))
    base_pdb_names = {os.path.basename(x) for x in pdb_paths}
    cache_path = os.path.join(pdb_dir, 'distances.pkl')
    restraints_path = workspace.restraints_path

    if use_cache and os.path.exists(cache_path):
        cached_records = pd.read_pickle(cache_path).to_dict('records')
        cached_paths = {x['path'] for x in cached_records}
        uncached_paths = [
                pdb_path for pdb_path in pdb_paths
                if os.path.basename(pdb_path) not in cached_paths]
    else:
        cached_records = []
        uncached_paths = pdb_paths

    uncached_records = read_and_calculate(uncached_paths, restraints_path)

    distances = pd.DataFrame(cached_records + uncached_records)
    distances.to_pickle(cache_path)
    return distances

def read_and_calculate(pdb_paths, restraints_path):
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

    # Read distances.

    records = []
    from scipy.spatial.distance import euclidean

    for i, path in enumerate(pdb_paths):
        sys.stdout.write("\rReading '{}' [{}/{}]".format(
            os.path.dirname(path), i+1, len(pdb_paths)))
        sys.stdout.flush()

        record = {'path': os.path.basename(path)}
        restraint_distances = []

        with gzip.open(path) as file:
            lines = file.readlines()

        for line in lines:
            if line.startswith('total_score'):
                record['score'] = float(line.split()[1])

            if line.startswith('loop_backbone_rmsd'):
                record['loop_dist'] = float(line.split()[1])

            if line.startswith('delta_buried_unsats'):
                record['delta_unsats'] = float(line.split()[1])

            if line.startswith('ATOM'):
                atom_name = line[13:16].strip()
                residue_id = line[22:26].strip()

                for restraint in restraints:
                    if (restraint.residue_id == residue_id and
                            restraint.atom_name == atom_name):
                        position = xyz_to_array(line[30:54].split())
                        distance = euclidean(restraint.position, position)
                        restraint_distances.append(distance)

        record['restraint_dist'] = np.mean(restraint_distances)
        records.append(record)

    sys.stdout.write('\n')
    return records

def xyz_to_array(xyz):
    return np.array([float(x) for x in xyz])


