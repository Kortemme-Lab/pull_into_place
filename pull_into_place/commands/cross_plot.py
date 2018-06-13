#!/usr/bin/env python2
# encoding: utf-8

"""
Plot one structures from one step against an average of child designs in
a later step. 

Usage:
    pull_into_place cross_plot <directory1> <directory2> [options]

Options:
    --force, -f
        Force PIP to recalculate the tree.

"""

from pull_into_place import trees, pipeline
from klab import docopt
import show_my_designs as smd
import yaml, os

"""
Psuedo-code for figuring out parent/child relationships

def nuclear_familyi(num_levels):
    for child in child_directory:
        parent = child
        for i in range(0, num_levels):
            parent = parent.up
        dict[parent].append(child)

for parent in dict:
    design = CrossDesign(parent, children)
"""


def main():
    
    args = docopt.docopt(__doc__)

    parent_directory = args['<directory1>']
    child_directory = args['<directory2>']

    force = args['--force']

    parent_workspace = pipeline.workspace_from_dir(parent_directory)
    child_workspace = pipeline.workspace_from_dir(child_directory)
    tree = trees.load_tree(child_workspace,force)

    ws = child_workspace
    tree_levels = 0
    while ws != parent_workspace:
        ws = ws.predecessor
        tree_levels += 1

class CrossDesign(smd.Design):

    def __init__(self, parent_directory, child_directory,
            tree, tree_levels, use_cache=True):
        self.directory = child_directory
        self.parent_directory = parent_directory
        self.cache_path = os.path.join(directory, 'models.pkl')
        self.parent_cache_path = os.path.join(parent_directory,
        'models.pkl')
        self.notes_path = os.path.join(directory, 'notes.txt')
        self.rep_path = os.path.join(directory, 'representative.txt')
        self._models = None
        self._metrics = {}
        self._notes = ""
        self._representative = None

        self.tree = tree
        self.tree_levels = tree_levels

        self._load_models(use_cache,tree,tree_levels)
        self._load_annotations()

    def _load_models(self, use_cache): #
        self._models, self._metrics = structures.load(
                self.directory,
                use_cache=use_cache,
                require_io_dir=False,
        )

    def _load_parent_model(self, use_cache):
        """
        Load a variety of score and distance metrics for the parent
        structure.
         
        Note: May want to load the entire parent directory, just so I
        can use structures.load(). Then, use another variable set in
        __init__ to get the info for the parent STRUCTURE. 

        Note 2: read_and_calculate(workspace, [parent_directory]) will
        also work.
        """

        # Make sure that the given path exists.
        if not os.path.exists(self.parent_directory):
            raise IOError("'{}' doe snot exist".format(self.directory))
        
        if use_cache and os.path.exists(self.parent_cache_path):
            cached_records = pd.read_pickle(self.cache_path).to_dict('records')
            cached_paths = set(
                    record['path'] for record in cached_records
                    if 'path' in record)
            uncached_paths = [
                    pdb_path for pdb_path in pdb_paths
                    if os.path.basename(pdb_path) not in cached_paths]

        else:
            cached_records = []
            uncached_paths = pdb_paths
class CrossPlotSMD(ShowMyDesigns):
    # Changes to make it a swarm plot

    def plot_models(self, axes, designs, **kwargs):
        
        from itertools import count
        import seaborn as sns

        labels = kwargs.get('labels', None)
        x_metric = kwargs.get('x_metric', self.x_metric)
        y_metric = kwargs.get('y_metric', self.y_metric)

        # Define the colors that the plot will use.

        red =    '#ef2929', '#cc0000', '#a40000'
        orange = '#fcaf3e', '#f57900', '#ce5c00'
        yellow = '#fce94f', '#edd400', '#c4a000'
        green =  '#8ae234', '#73d216', '#4e9a06'
        blue =   '#729fcf', '#3465a4', '#204a87'
        purple = '#ad7fa8', '#75507b', '#5c3566'
        brown =  '#e9b96e', '#c17d11', '#8f5902'
        grey =   '#2e3436', '#555753', '#888a85', '#babdb6', '#d3d7cf', '#eeeeec'

        def color_from_cycle(index): #
            cycle = (blue[1], red[1], green[2], orange[1], purple[1], brown[1],
                     blue[0], red[0], green[1], orange[0], purple[0], brown[0])
            return cycle[index % len(cycle)]

        # Clear the axes and reset the axis labels

        axes.clear()
        axes.set_xlabel(self.metrics[x_metric].title)
        axes.set_ylabel(self.metrics[y_metric].title)

        # Plot the two axes.

        for index, design in enumerate(designs):
            rep = design.representative
            color = color_from_cycle(index)
            label = labels[index] if labels is not None else ''
            action = self.filter_pane.get_action()
            keep, drop = self.filter_pane.get_masks(design)

            x = design.get_metric(x_metric)
            y = design.get_metric(y_metric)

            # Scale the size of the points by the number of points.
            size = np.clip(7500 / max(len(x), 1), 2, 15)

            # Highlight the representative model.
            if keep[rep]:
                axes.scatter(
                        [x[rep]], [y[rep]],
                        s=60, c=yellow[1], marker='o', edgecolor='none',
                        label='_nolabel_')

            # Highlight the filtered points, if that's what the user wants.
            if action == 'highlight':
                axes.scatter(
                        x[drop], y[drop],
                        s=size, c=grey[4], marker='o', edgecolor='none',
                        label='_nolabel_')

            # Draw the whole score vs distance plot.
            lines = axes.scatter(
                    x[keep], y[keep],
                    s=size, c=color, marker='o', edgecolor='none',
                    label=label, picker=True)

            lines.paths = design.paths
            lines.design = design

        # Pick the axis limits based on the range of every design.  This is done
        # so you can scroll though every design without the axes changing size.
