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

from pull_into_place import trees, pipeline, structures
from klab import docopt
import show_my_designs as smd
import numpy as np
import yaml, os, gtk, collections

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
    while ws.focus_dir != parent_workspace.focus_dir:
        ws = ws.predecessor
        tree_levels += 1

class CrossDesign(smd.Design):

    def __init__(self, child_directory,
            tree, tree_levels, use_cache=True):
        self.directory = os.path.abspath(child_directory)
        self.cache_path = os.path.join(child_directory, 'models.pkl')
        self.notes_path = os.path.join(child_directory, 'cross_notes.txt')
        self.rep_path = os.path.join(child_directory, 'representative.txt')
        self._models = None
        self._metrics = {}
        self._notes = ""
        self._representative = None

        self.tree = tree
        self.tree_levels = tree_levels

        self._load_models(use_cache)
        self._load_annotations()
        self._load_metrics()

    def get_parent_models(self):
        # Need to make sure we only search_by_records once; relatively expensive
        nodes = trees.search_by_records(self.tree,{'directory':self.directory})
       
        for i in range(0,len(self._models)):
            # Looping through nodes also somewhat expensive, but I don't see
            # another way of doing this right now.
            for node in nodes:
                if node.records['full_path'] == self._models.loc[i,'full_path']:
                    parent = self.go_to_parent_node(node)
                    for metric in parent.records:
                        self._models.loc[i,'parent_' + metric] = \
                                parent.records[metric]
        
    def go_to_parent_node(self, node):
        for i in range(0, self.tree_levels):
            node = node.up
        return node

    def _load_models(self, use_cache): #
        self._models, self._metrics = structures.load(
                self.directory,
                use_cache=use_cache,
                require_io_dir=False,
        )

        self.get_parent_models()


class CrossPlotSMD(smd.ShowMyDesigns):
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

            sns.set_style("whitegrid")
            sns.swarmplot(x=x_metric, y=y_metric,
                    data=design._models, ax=axes)
            """
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
            """

        # Pick the axis limits based on the range of every design.  This is done
        # so you can scroll though every design without the axes changing size.

        if self.is_legend_visible:
            axes.legend(loc='upper right')

        if self.is_model_count_visible:
            axes.annotate(
                    ', '.join(str(len(x)) for x in designs),
                    xy=(0, 1), xycoords='axes fraction',
                    xytext=(8, -8), textcoords='offset points',
                    verticalalignment='top',
            )

def show_my_designs(directories, tree, tree_levels, use_cache=True, launch_gui=True,
        fork_gui=True ):
    try:
        try:
            designs = load_designs(directories, tree, tree_levels, use_cache=use_cache)
        except IOError as error:
            if str(error):
                print "Error:", str(error)
                sys.exit()
            else:
                raise

        if designs and launch_gui:
            # If the user wants to run in a background process, try to fork.
            # But for some reason fork() doesn't seem to work on Macs, so just
            # run the GUI in the main process if anything goes wrong.
            try:
                if fork_gui and os.fork():
                    sys.exit()
            except Exception:
                pass

            gui = CrossPlotSMD(designs)
            gtk.main()

    except KeyboardInterrupt:
        print

def load_designs(directories, tree, tree_levels, use_cache=True):
    designs = collections.OrderedDict()

    for directory in directories:
        designs[directory] = CrossDesign(directory, tree, tree_levels,use_cache)

    return designs
