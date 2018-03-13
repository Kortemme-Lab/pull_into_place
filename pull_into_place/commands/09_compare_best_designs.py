#!/usr/bin/env python2
# encoding: utf-8

"""\
Create a nicely organized excel spreadsheet comparing all of the validated
designs in the given workspace where the lowest scoring decoy within some
threshold of the target structure.

Usage:
    pull_into_place 09_compare_best_designs <workspace> [<round>] [options]

Options:
    -t, --threshold RESTRAINT_DIST   [default: 1.2]
        Only consider designs where the lowest scoring decoy has a restraint
        satisfaction distance less than the given threshold.

    -u, --structure-threshold LOOP_RMSD
        Limit how different two loops can be before they are placed in
        different clusters by the structural clustering algorithm.

    -q, --num-sequence-clusters NUM_CLUSTERS   [default: 0]
        Specify how many sequence clusters should be created.  If 0, the
        algorithms will try to detect the number of clusters that best matches
        the data on its own.

    -s, --subs-matrix NAME   [default: blosum80]
        Specify a substitution matrix to use for the sequence clustering
        metric.  Any name that is understood by biopython may be used.  This
        includes a lot of the BLOSUM and PAM matrices.

    -p, --prefix PREFIX
        Specify a prefix to append to all the files generated by this script.
        This is useful for discriminating files generated by different runs.

    -v, --verbose
        Output sanity checks and debugging information for each calculation.
"""

from __future__ import division

import os, re, sys, string, itertools, yaml, numpy as np
from klab import docopt, scripting
from .. import pipeline, structures

class Metric (object):
    """
    The metric classes each represent a way of comparing different validated
    designs, or a single column in the spreadsheet produced by this script.
    The script will begin by calling the load() method for each metric.
    Subclasses should overload this method and use it to calculate values for
    each design.  If each design can be considered separately, it may be easier
    to overload load_cell() instead of load() itself.  Once that is done, the
    remaining methods will be called to fill out the spreadsheet.

    The face_value() method should reimplemented to return the value to
    display in the spreadsheet.  The score_value() method should return a
    value that can be used to sort the designs from best to worst.  Bigger
    numbers are taken to be better.  By default score_value() returns the same
    thing as face_value(), but metrics where smaller numbers are better (e.g.
    RMSD) may have to overload score_value() to flip the sign.  The compare()
    method calls score_value() to determine which of two designs is "better" by
    the metric in question.

    The header_format() and cell_format() methods use a lot of the information
    that can be specified using the class variable defined below to return
    dictionaries describing how the metric's column should be formatted.  These
    methods can also be reimplemented, if so desired.
    """
    title = "Unnamed Metric"
    align = "left"
    width = 18
    color = False
    num_format = None
    font_name = None
    format = {}
    progress_update = None

    def load(self, designs, verbose=False):
        for design in designs:
            self.load_cell(design, verbose)

    def load_cell(self, design, verbose=False):
        pass

    def compare(self, design_1, design_2):
        return self.score_value(design_1) < self.score_value(design_2)

    def face_value(self, design):
        raise NotImplementedError

    def score_value(self, design):
        return self.face_value(design)

    def header_format(self):
        format = dict(bold=True, italic=True)
        if self.align is not None: format['align'] = self.align
        return format

    def cell_format(self):
        format = self.format.copy()
        if self.align is not None: format['align'] = self.align
        if self.num_format is not None: format['num_format'] = self.num_format
        if self.font_name is not None: format['font_name'] = self.font_name
        return format


class DesignNameMetric (Metric):
    """
    Make a column that just lists the name of each design.
    """
    title = "Design Name"
    align = 'left'
    width = 25

    def load_cell(self, design, verbose=False):
        round = re.search('round_(\d+)', design.directory).group(1)
        name = design['path'][design.rep][:-len('.pdb.gz')]
        design.name = "Round {}: {}".format(round, name)

    def face_value(self, design):
        return design.name


class ResfileSequenceMetric (Metric):
    """
    Make a column that shows the amino acid identities of the positions that
    were allowed to design.
    """
    title = "Resfile Sequence"
    align = 'left'
    font_name = 'Monospace'
    width = 30

    def face_value(self, design):
        return design.resfile_sequence


class SequenceClusterMetric (Metric):
    """
    Make a column that shows which designs have the most similar sequences.
    Only positions that were allowed to design are considered in this
    clustering, and no alignment is done.  The sequences are simply compared
    using a score matrix like BLOSUM80.
    """
    title = "Sequence Cluster"
    progress_update = "Clustering sequences..."
    align = 'center'
    num_format = '0'

    def __init__(self, matrix_name):
        from klab.bio.subs_matrix import load_subs_matrix
        self.subs_matrix = load_subs_matrix(matrix_name)

    def load(self, designs, verbose=False):
        self._cluster_hierarchically(designs, verbose)

    def face_value(self, design):
        return design.sequence_cluster

    def _cluster_by_k_mediods(self, designs, verbose=False):
        raise NotImplementedError

    def _cluster_hierarchically(self, designs, verbose=False):
        import scipy.spatial.distance as sp_dist
        import scipy.cluster.hierarchy as sp_clust
        from itertools import combinations

        num_designs = len(designs)
        if num_designs < 2: return

        dist_matrix = self._get_pairwise_distance_matrix(designs)
        dist_vector = sp_dist.squareform(dist_matrix)
        mean_dist = np.mean(dist_vector)
        hierarchy = sp_clust.complete(dist_vector)
        clusters = sp_clust.fcluster(
                hierarchy, mean_dist, criterion='distance')

        for cluster, design in zip(clusters, designs):
            design.sequence_cluster = cluster

        if verbose:
            import pylab
            print "Made {} clusters.".format(len(set(clusters)))
            pylab.hist(dist_vector, bins=100)
            pylab.axvline(mean_dist)
            pylab.show()

    def _cluster_by_dbscan(self, designs, verbose=False):
        from sklearn.cluster import DBSCAN
        from pprint import pprint

        num_designs = len(designs)
        if num_designs < 2: return

        dist_matrix = self._get_pariwise_distance_matrix(designs)

        # Predict a reasonable set of parameters for the DBSCAN algorithm.

        # min_pts: The minimum cluster size, roughly speaking.  The more
        # precise definition of this parameter is the number of points that
        # have to be within eps (see below) of a point in order to seed a
        # cluster.  This option can be controlled by the user, but the default
        # is simply a fraction of the total number of designs.

        min_pts = len(designs) // 20

        # eps: The distance within which points are considered to be part of
        # the same cluster.  This is not user controllable and is picked by
        # looking at the distribution of distances between each point and its
        # min_pts nearest neighbor.

        k_dist = np.sort(dist_matrix, axis=0)[min_pts]
        eps = np.mean(k_dist)

        # Cluster the sequences using DBSCAN.  DBSCAN is a nice algorithm
        # because it automatically determines the appropriate number of
        # clusters to best match the data.

        kernel = DBSCAN(eps, min_pts, metric='precomputed')
        labels = kernel.fit_predict(dist_matrix)
        next_outlier_label = max(labels) + 1

        for label, design in zip(labels, designs):
            design.sequence_cluster = label

            # DBSCAN uses -1 to label outliers, i.e. points that don't fit into
            # any cluster.  Relabel these designs so that they each appear to
            # be in their own cluster.

            if design.sequence_cluster == -1:
                design.sequence_cluster = next_outlier_label
                next_outlier_label += 1

        if verbose:
            print 'DBSCAN Parameters:'
            print '  min_pts:', min_pts
            print '  eps:', eps
            print '  num clusters:', len(set(labels)) - 1

            import pylab
            pylab.hist(k_dist, bins=len(k_dist)/5)
            pylab.axvline(eps)
            pylab.show()

    def _get_pairwise_distance_matrix(self, designs):
        from klab.bio.subs_matrix import score_gap_free_alignment

        dist_matrix = np.zeros((len(designs), len(designs)))
        design_combos = itertools.combinations(enumerate(designs), 2)

        for (i, design_i), (j, design_j) in design_combos:
            seq_i, seq_j = design_i.resfile_sequence, design_j.resfile_sequence
            dist_matrix[i,j] = score_gap_free_alignment(seq_i, seq_j, self.subs_matrix)
            dist_matrix[j,i] = dist_matrix[i,j]

        return dist_matrix


class StructureClusterMetric (Metric):
    """
    Make a column that shows which designs are the most structurally similar.
    This metric works by creating a hierarchical clustering of all the design
    "representatives" based on loop backbone RMSD.  Clusters are then made such
    that every member in every cluster is within a certain loop RMSD of all its
    peers.  This column is nice because it makes it easier to compare apples to
    apples, as it were.
    """
    title = "Struct Cluster"
    progress_update = "Clustering loops..."
    align = 'center'
    num_format = '0'

    def __init__(self, threshold=None):
        self.threshold = threshold

    def load(self, designs, verbose=False):
        for design in designs: self.read_loop_coords(design)
        self.cluster_loop_coords(designs, verbose)

    def face_value(self, design):
        return design.structure_cluster

    def read_loop_coords(self, design):
        if design.rep_path.endswith('.gz'):
            from gzip import open
        else:
            from __builtin__ import open

        with open(design.rep_path) as file:
            lines = file.readlines()

        loop_coords = []
        loop_indices = []
        backbone_atoms = 'N', 'CA', 'C'

        for start, stop in design.loops:
            loop_indices += range(start, stop + 1)

        for line in lines:
            if line[0:6] != 'ATOM  ': continue

            atom_name = line[13:16].strip().upper()
            residue_id = int(line[22:26])
            atom_coord = np.array((
                    float(line[30:38]),
                    float(line[38:46]),
                    float(line[46:54])))

            if residue_id in loop_indices and atom_name in backbone_atoms:
                loop_coords.append(atom_coord)

        design.loop_coords = np.asarray(loop_coords)

    def cluster_loop_coords(self, designs, verbose=False):
        import scipy.spatial.distance as sp_dist
        import scipy.cluster.hierarchy as sp_clust
        from itertools import combinations

        num_designs = len(designs)
        if num_designs < 2: return

        # Calculate the pairwise distance matrix.

        dist_matrix = np.zeros((num_designs, num_designs))
        design_combos = itertools.combinations(enumerate(designs), 2)

        for (i, design_i), (j, design_j) in design_combos:
            dist_matrix[i,j] = self.calculate_loop_rmsd(design_i, design_j)
            dist_matrix[j,i] = dist_matrix[i,j]

        # Cluster the design such that no two designs in any cluster are
        # further apart than the given threshold.  The user can specify this
        # threshold using the --structure-threshold option.  The default of
        # 1.0Å is arbitrary, but it seems to work well for most cases.

        dist_vector = sp_dist.squareform(dist_matrix)
        mean_dist = np.mean(dist_vector)
        hierarchy = sp_clust.complete(dist_vector)
        clusters = sp_clust.fcluster(
                hierarchy, self.threshold or mean_dist, criterion='distance')

        for cluster, design in zip(clusters, designs):
            design.structure_cluster = cluster

        # Print some debugging information, if requested.

        if verbose == True:
            cluster_map = {}

            for cluster, design in zip(clusters, designs):
                cluster_map.setdefault(cluster, []).append(design)

            for cluster in sorted(set(clusters)):

                # Print out the designs contained in this cluster.

                print "Cluster {}:".format(cluster)
                for design in cluster_map[cluster]:
                    print " ", design.rep_path
                print

                # Print out pairwise distances for every cluster member.

                X = cluster_map[cluster]
                N = len(X)
                D = np.zeros((N, N))

                for i, design_i in enumerate(X):
                    for j, design_j in enumerate(X):
                        D[i,j] = self.calculate_loop_rmsd(design_i, design_j)

                print sp_dist.squareform(D)
                print

                # Offer to display the cluster in pymol.

                command = ['pymol', '-qx']
                for design in cluster_map[cluster]:
                    command.append(design.rep_path)

                if raw_input("  View in pymol? [y/N] ") == 'y':
                    import subprocess
                    subprocess.check_output(command)

                print

    def calculate_loop_rmsd(self, design_1, design_2):
        assert len(design_1.loop_coords) and len(design_2.loop_coords)
        difference = design_1.loop_coords - design_2.loop_coords
        num_atoms = design_1.loop_coords.shape[0]
        return np.sqrt(np.sum(difference**2) / num_atoms)


class RestraintDistMetric (Metric):
    """
    Make a column that shows how well each design satisfies the design goal.
    """
    title = u"Restraint Dist (Å)"
    progress_update = "Calculating quality metrics..."
    align = 'center'
    num_format = '0.00'
    color = True

    def load_cell(self, design, verbose=False):
        design.restraint_dist = design.rep_distance

    def face_value(self, design):
        return design.restraint_dist

    def score_value(self, design):
        return -self.face_value(design)


class ScoreGapMetric (Metric):
    """
    Make a column that shows the difference in score between the lowest scoring
    models with restraint distances less than and greater than 1Å and 2Å,
    respectively.  This is a rough way to get an idea for how deep the score
    vs. RMSD funnel is for each design.
    """
    title = "Score Gap (REU)"
    align = 'center'
    num_format = '0.00'
    color = True

    def load_cell(self, design, verbose=False):
        scores = design.structures['total_score']
        distances = design.structures['restraint_dist']
        rep_score = design.structures['total_score'][design.rep]

        competitor_scores = scores.copy()
        competitor_scores[distances < 2.0] = np.inf
        competitor = np.argmin(competitor_scores)
        competitor_score = design.scores[competitor]

        design.score_gap = competitor_score - rep_score

    def face_value(self, design):
        return design.score_gap


class PercentSubangstromMetric (Metric):
    """
    Make a column that shows what percent of the validation run predictions had
    sub-angstrom restraint distances.
    """
    title = "% Subangstrom"
    align = 'center'
    num_format = '0.00'
    color = True

    def load_cell(self, design, verbose=False):
        distances = design.structures['restraint_dist']
        suba_distances = distances[distances < 1.0]
        design.percent_subangstrom = 100 * len(suba_distances) / len(distances)

    def face_value(self, design):
        return design.percent_subangstrom


class BuriedUnsatHbondMetric (Metric):
    """
    Make a column that shows how many buried unsatisfied H-bonds each design
    has.  This is something that is not accounted for by the rosetta function,
    but can do a very good job discriminating reasonable backbones from
    horrible ones.
    """
    title = "# Buried Unsats"
    align = 'center'
    num_format = '"+"0;"-"0'
    color = True

    def load_cell(self, design, verbose=False):
        design.buried_unsats = \
                design.structures['buried_unsat_score'][design.rep]

    def face_value(self, design):
        return design.buried_unsats

    def score_value(self, design):
        return -self.face_value(design)


class DunbrackScoreMetric (Metric):
    """
    Make a column that shows the Dunbrack score for each residue that was part
    of the design goal (i.e. was restrained in the building step).  High
    Dunbrack scores indicate unlikely sidechain conformations.
    """
    title = "Dunbrack (REU)"
    align = 'center'
    num_format = '0.00'
    color = True

    def load_cell(self, design, verbose=False):
        design.dunbrack_score = \
                design.structures['dunbrack_score'][design.rep]

    def face_value(self, design):
        return design.dunbrack_score

    def score_value(self, design):
        return -self.face_value(design)



class ExtraFilterHandler (Metric):
    """
    Class that handles filters input by the user. The user should put a "+" or "-"
    at the beginning of each filter name to define whether larger numbers (+) or
    smaller numbers (-) are better. Used to make an excel column for
    extra filters.
    """

    def __init__(self, filtername):
        align = 'center'
        num_format = '0.000'
        self.filtername = filtername
        meta = structures.parse_filter(filtername)
        self.title = meta.name
        self.direction = meta.direction
        if self.direction:
            self.color = True

    def face_value(self,design):
        return design[self.filtername][design.rep]

    def score_value(self,design):
        if self.direction == '-':
            scorevalue = -self.face_value(design)
        else:
            scorevalue = self.face_value(design)
        return scorevalue



def find_validation_workspaces(name, round=None):
    """
    Find all the workspaces containing validated designs.
    """
    workspaces = []

    for round in [round] if round else itertools.count(1):
        workspace = pipeline.ValidatedDesigns(name, round)
        if not workspace.exists(): break
        workspaces.append(workspace)

    if not workspaces:
        scripting.print_error_and_die('No validated designs found.')

    return workspaces

def find_reasonable_designs(workspaces, threshold=None, verbose=False):
    """
    Return a list of design where the representative model has a restraint
    distance less that the given threshold.  The default threshold (1.2) is
    fairly lenient.
    """
    print "Loading designs..."

    designs = []

    if threshold is None:
        threshold = 1.2

    for workspace in workspaces:
        for directory in workspace.output_subdirs:
            if verbose:
                print '  ' + directory
            design = structures.Design(directory)
            if design.rep_distance < float(threshold):
                designs.append(design)

    return designs

def discover_custom_metrics(metrics, workspaces):
    """
    Look for additional quality metrics in the current working directory or in
    any of the given workspaces.  Only scripts named 'custom_metrics.py' will
    be searched.

    What will the API of custom_metrics.py be?
    How will command-line arguments be passed to these metrics?
    """
    pass

def calculate_quality_metrics(metrics, designs, verbose=False):
    """
    Have each metric calculate all the information it needs.
    """
    for metric in metrics:
        if metric.progress_update:
            print metric.progress_update
        metric.load(designs, verbose)

def find_pareto_optimal_designs(designs, metrics, verbose=False):
    """
    Prune designs that are not on the Pareto front.  In other words, we want to
    get rid of designs that are worse by every metric to at least one other
    design.  The idea is that we would never want to use these designs, because
    we would instead use the one that is better in every way.

    Currently this method is a no-op, because I didn't have the energy to
    actually implement it.  If you really need this feature, you should be able
    to write it here and plug it in with no issue.
    """
    return designs


def report_quality_metrics(designs, metrics, path, clustering=False):
    """
    Create a nicely formatted spreadsheet showing all the designs and metrics.
    """
    import xlsxwriter
    print "Reporting quality metrics..."

    # Open a XLSX worksheet.

    workbook = xlsxwriter.Workbook(path)
    worksheet = workbook.add_worksheet()

    workbook.formats[0].border = 1
    workbook.formats[0].border_color = 'gray'

    # Setup the cell background color highlights.

    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import LinearSegmentedColormap

    best_color = np.array([114, 159, 207]) / 255    # Tango light blue
    worst_color = np.array([255, 255, 255]) / 255
    color_table = {
            'red':   [(0.0, worst_color[0], worst_color[0]),
                      (1.0,  best_color[0],  best_color[0])],
            'green': [(0.0, worst_color[1], worst_color[1]),
                      (1.0,  best_color[1],  best_color[1])],
            'blue':  [(0.0, worst_color[2], worst_color[2]),
                      (1.0,  best_color[2],  best_color[2])],
    }
    color_map = LinearSegmentedColormap('highlight', color_table)

    # Write the header row.
    for col, metric in enumerate(metrics):
        cell = xlsxwriter.utility.xl_col_to_name(col) + '1'
        format = workbook.add_format(metric.header_format())
        worksheet.write(cell, metric.title, format)
        worksheet.set_column(col, col, metric.width)

    # Write the data rows.

    designs = designs[:]
    designs.sort(key=lambda x: x.restraint_dist)
    designs.sort(key=lambda x: x.buried_unsats)
    designs.sort(key=lambda x: x.sequence_cluster)

    for col, metric in enumerate(metrics):
        face_values = np.array([metric.face_value(x) for x in designs])
        score_values = np.array([metric.score_value(x) for x in designs])
        cell_format = metric.cell_format()

        if metric.color:
            color_spectrum = ScalarMappable(cmap=color_map)
            rgba = (255 * color_spectrum.to_rgba(score_values)).astype(int)
            colors = ['#{:02x}{:02x}{:02x}'.format(*x) for x in rgba]

        for index, face_value in enumerate(face_values):
            if metric.color:
                cell_format.update({
                    'bg_color': colors[index],
                    'border_color': '#c7c7c7',
                    'border': 1 })

            format_handle = workbook.add_format(cell_format)
            worksheet.write(index + 1, col, face_value, format_handle)

    # Write the XLSX file.

    workbook.close()

def report_score_vs_rmsd_funnels(designs, path):
    """
    Create a PDF showing the score vs. RMSD funnels for all the reasonable
    designs.  This method was copied from an old version of this script, and
    does not currently work.
    """
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt

    print "Reporting score vs RMSD funnels..."

    pdf = PdfPages(path)
    designs = sorted(designs, key=lambda x: x.fancy_path)

    for index, design in enumerate(designs):
        plt.figure(figsize=(8.5, 11))
        plt.suptitle(design.fancy_path)

        axes = plt.subplot(2, 1, 1)
        plot_score_vs_dist(axes, design, metric="Max COOH Distance")

        axes = plt.subplot(2, 1, 2)
        plot_score_vs_dist(axes, design, metric="Loop RMSD")

        pdf.savefig(orientation='portrait')
        plt.close()

    pdf.close()

def report_pymol_sessions(designs, directory):
    """
    Create pymol session for each reasonable design representative.  This
    method was copied from an old version of this script, and does not
    currently work.
    """
    print "Reporting pymol sessions..."

    if os.path.exists(directory): shutil.rmtree(directory)
    os.mkdir(directory)

    with open('pymol_modes.txt') as file:
        import yaml
        base_config = yaml.load_cell(file)['Present design in pymol']

    for design in designs:
        decoy = design.representative
        config = base_config + ' save ' + os.path.join(
                directory, design.get_fancy_path('.pse')) + ';'

        score_vs_distance.open_in_pymol(design, decoy, config, gui=False)

def annotate_designs(designs):
    """
    Automatically annotate the sequence and structure cluster for all the
    reasonable designs identified by this script.  These annotations make it
    easier to quickly focus on interesting subsets of design in the "Show My
    Designs" GUI.
    """
    for design in designs:
        annotation = '+ seq{} struct{}'.format(
                design.sequence_cluster, design.structure_cluster)

        # Find any existing annotations.

        annotation_path = os.path.join(design.directory, 'notes.txt')

        try:
            with open(annotation_path) as file:
                annotation_lines = file.readlines()
        except IOError:
            annotation_lines = []

        # If there are existing annotations and the first line starts with a
        # plus, assume that the line was previously inserted by this function
        # and should now be updated with the most recent information.

        if annotation_lines and annotation_lines[0].startswith('+'):
            annotation_lines[0] = annotation

        # Otherwise, insert the annotation above the existing lines.

        else:
            annotation_lines.insert(0, annotation)

        with open(annotation_path, 'w') as file:
            file.write('\n'.join(annotation_lines))

def discover_filter_metrics(metrics,workspaces):
    for workspace in workspaces:
        filter_list = pipeline.workspace_from_dir(docopt.docopt(__doc__)['<workspace>']).filters_list
        filters = []
        with open(filter_list,"r") as file:
            filters = yaml.load(file)
        if filters:
            for record in filters:
                filterclass = ExtraFilterHandler(record)
                metrics.append(filterclass)

@scripting.catch_and_print_errors()
def main():

    args = docopt.docopt(__doc__)
    prefix = args['--prefix'] or ''
    workspaces = find_validation_workspaces(
            args['<workspace>'], args['<round>'])
    designs = find_reasonable_designs(
            workspaces, args['--threshold'], args['--verbose'])
    metrics = [
            DesignNameMetric(),
            ResfileSequenceMetric(),
            SequenceClusterMetric(args['--subs-matrix']),
            StructureClusterMetric(args['--structure-threshold']),
            RestraintDistMetric(),
            ScoreGapMetric(),
            PercentSubangstromMetric(),
            BuriedUnsatHbondMetric(),
            DunbrackScoreMetric(),
    ]


    discover_filter_metrics(metrics, workspaces)
    #discover_custom_metrics(metrics, workspaces)
    calculate_quality_metrics(metrics, designs, args['--verbose'])
    designs = find_pareto_optimal_designs(designs, metrics, args['--verbose'])
    report_quality_metrics(designs, metrics, prefix + 'quality_metrics.xlsx')
    #report_score_vs_rmsd_funnels(designs, prefix + 'score_vs_rmsd.pdf')
    #report_pymol_sessions(designs, prefix + 'pymol_sessions')
    annotate_designs(designs)
