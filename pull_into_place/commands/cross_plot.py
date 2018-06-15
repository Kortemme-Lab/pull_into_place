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
import seaborn as sns
import numpy as np
import pandas as pd
import yaml, os, gtk, collections,sys
from show_my_designs.gui import try_to_run_command

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

        from sys import stdout
       
        for i in range(0,len(self._models)):
            stdout.write("\rFinding parent metrics for model {} of \
{}".format(i, len(self._models)))
            stdout.flush()
            # Looping through nodes also somewhat expensive, but I don't see
            # another way of doing this right now.
            for node in nodes:
                if node.records['full_path'] == self._models.loc[i,'full_path']:
                    parent = self.go_to_parent_node(node)
                    self.add_parent_metrics(i,parent)
                    if not (self._models['full_path'] ==
                            parent.records['full_path']).any():
                        parent_index = len(self._models)
                        # Add parent to records so we can plot that as
                        # well. 
                        parent_dict = {}
                        for metric in parent.records:
                            parent_dict[metric] = parent.records[metric]
                        parent_df =\
                                pd.DataFrame([parent_dict],index=[parent_index])
                        self._models =\
                                pd.concat([self._models,parent_df])
                        self.add_parent_metrics(parent_index, parent)
                        self._models.loc[parent_index, 'is_parent'] = True
                        
        
    def go_to_parent_node(self, node):
        for i in range(0, self.tree_levels):
            node = node.up
        return node

    def add_parent_metrics(self, index, parent_node, prefix='parent_'):
        for metric in parent_node.records:
            self._models.loc[index, prefix + metric] = \
                    parent_node.records[metric]

    def _load_models(self, use_cache): #
        self._models, self._metrics = structures.load(
                self.directory,
                use_cache=use_cache,
                require_io_dir=False,
        )
        self._models['is_parent'] = False

        cache_path = os.path.join(self.directory,
                'crossplot_{}_levels.pkl'.format(self.tree_levels))

        if use_cache and os.path.exists(cache_path):
            cached_records = pd.read_pickle(cache_path)
            self._models = cached_records

        else:
            self.get_parent_models()
            self._models.to_pickle(cache_path)



def swarmplot(design,x=None, y=None, hue=None, data=None, order=None, hue_order=None,
              dodge=False, orient=None, color=None, palette=None,
              size=5, edgecolor="gray", linewidth=0, ax=None, **kwargs):

    if "split" in kwargs:
        dodge = kwargs.pop("split")
        msg = "The `split` parameter has been renamed to `dodge`."
        warnings.warn(msg, UserWarning)

    plotter = SwarmPlotter(design, x, y, hue, data, order, hue_order,
                            dodge, orient, color, palette)
    if ax is None:
        ax = plt.gca()

    kwargs.setdefault("zorder", 3)
    size = kwargs.get("s", size)
    if linewidth is None:
        linewidth = size / 10
    if edgecolor == "gray":
        edgecolor = plotter.gray
    kwargs.update(dict(s=size ** 2,
                       edgecolor=edgecolor,
                       linewidth=linewidth))

    plotter.plot(ax, kwargs)
    return ax

class CrossPlotSMD(smd.ShowMyDesigns):
    # Changes to make it a swarm plot

    def plot_models(self, axes, designs, **kwargs):
        
        from itertools import count

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

        def palette_from_cycle(index): #
            cycle = (blue[1], red[1], green[2], orange[1], purple[1], brown[1],
                     blue[0], red[0], green[1], orange[0], purple[0], brown[0])
            
            index = index * 2
            index %= len(cycle)
            return cycle[index:] + cycle[:index]

        # Clear the axes and reset the axis labels

        axes.clear()
        axes.set_xlabel(self.metrics[x_metric].title)
        axes.set_ylabel(self.metrics[y_metric].title)

        # Plot the two axes.

        for index, design in enumerate(designs):
            rep = design.representative
            color = color_from_cycle(index)
            palette = palette_from_cycle(index)
            label = labels[index] if labels is not None else ''
            action = self.filter_pane.get_action()
            keep, drop = self.filter_pane.get_masks(design)

            
            x = design.get_metric(x_metric)
            y = design.get_metric(y_metric)
            
            size = np.clip(7500 / max(len(x), 1), 2, 15)
            sns.set_style("whitegrid")
            lines=swarmplot(design, x=x_metric, y=y_metric,
                    data=design._models, ax=axes,hue='is_parent',
                    palette=palette, label=label
                    )
           

            # Scale the size of the points by the number of points.
            """
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
 
    def on_click_plot_gtk(self, widget, event):
        import glob
        # Ignore any event that isn't a right button click or a left button
        # click with the control key held down.

        is_right_click = \
                (event.button == 3) or \
                (event.button == 1 and event.get_state() & gtk.gdk.CONTROL_MASK)

        if not is_right_click: return
        if self.toolbar._active == 'PAN': return
        if self.toolbar._active == 'ZOOM': return
        if self.selected_model is None: return

        # Figure out which model was clicked.

        index, design = self.selected_model
        pd.set_option("display.max_colwidth",1000)
        path = os.path.join(design.iloc[index]['directory'],
                design.iloc[index]['path'])
        #is_rep = (design['representative'] == index)
        self.selected_model = None

        # Search for scripts that can perform some action using the clicked
        # model.  Such scripts must have the `*.sho' suffix and may be located
        # anywhere from the directory containing the models to any directory
        # below that.  Any scripts that are found will be used to populate a
        # drop-down menu.  If selected, the script will be called with sh as
        # the interpreter and the path to the model as the singular argument.

        directory = os.path.abspath(design['directory'].to_string())
        sho_scripts = []

        while directory != os.path.abspath('/'):
            sho_pattern = os.path.join(directory, '*.sho')
            sho_scripts += glob.glob(sho_pattern)
            directory = os.path.dirname(directory)

        # Create and display the drop-down menu.

        file_menu = gtk.Menu()

        for script in sho_scripts:
            title = os.path.basename(os.path.splitext(script)[0])
            title = title[0].upper() + title[1:]
            title = title.replace('_', ' ')

            item = gtk.MenuItem(title)
            item.connect('activate',
                    lambda *args: try_to_run_command([script, path]))
            file_menu.append(item)

        view_in_pymol = gtk.MenuItem("View model in pymol")
        view_in_pymol.connect('activate',
                lambda *args: try_to_run_command(['pymol', path]))
        file_menu.append(view_in_pymol)

        view_in_chimera = gtk.MenuItem("View model in chimera")
        view_in_chimera.connect('activate',
                lambda *args: try_to_run_command(['chimera', path]))
        file_menu.append(view_in_chimera)

        file_menu.append(gtk.SeparatorMenuItem())

        copy_path = gtk.MenuItem("Copy path to model")
        copy_path.connect('activate', self.on_copy_model_path, path)
        file_menu.append(copy_path)

        """
        if index == design.representative:
            choose_rep = gtk.MenuItem("Reset representative")
            choose_rep.connect(
                'activate', self.on_set_representative, design, None)
        else:
            choose_rep = gtk.MenuItem("Set as representative")
            choose_rep.connect(
                'activate', self.on_set_representative, design, index)
        file_menu.append(choose_rep)
        """

        file_menu.foreach(lambda item: item.show())
        file_menu.popup(None, None, None, event.button, event.time)

class SwarmPlotter(sns.categorical._SwarmPlotter):
    
    def __init__(self, design, x, y, hue, data, order, hue_order,
                 dodge, orient, color, palette):
        """Initialize the plotter."""
        self.design = design
        self.data = data
        self.x = x
        self.y = y
        self.hue = hue
        self.establish_variables(x, y, hue, data, orient, order, hue_order)
        self.establish_colors(color, palette, 1)

        # Set object attributes
        self.dodge = dodge
        self.width = 5

    def draw_swarmplot(self, ax, kws):
        """Plot the data."""
        s = kws.pop("s")

        centers = []
        swarms = []

        # Set the categorical axes limits here for the swarm math
        #if not categorical_data:
        if self.orient == "v":
            ax.set_xlim(min(self.data[self.x]) - .5, max(self.data[self.x]) + .5)
        else:
            ax.set_ylim(min(self.data[self.y]), max(self.data[self.y]))
        """
        else:
            if self.orient == "v":
                ax.set_xlim(-.5, len(self.plot_data) - .5)
            else:
                ax.set_ylim(-.5, len(self.plot_data) - .5)
        """


        # Plot each swarm
        for i, group_data in enumerate(self.plot_data):

            group_y_data = np.array([hue for hue in group_data[self.y]])

            if self.plot_hues is None or not self.dodge:

                width = self.width

                if self.hue_names is None:
                    hue_mask = np.ones(group_data.size, np.bool)
                else:
                    hue_mask = np.zeros(len(self.plot_hues[i]), np.bool)
                    np_index = 0
                    for h in self.plot_hues[i].itertuples():
                        hue_mask[np_index] = getattr(h, self.hue) in \
                                self.hue_names
                    # Broken on older numpys
                    # hue_mask = np.in1d(self.plot_hues[i], self.hue_names)

                swarm_data = group_y_data[hue_mask]

                # Sort the points for the beeswarm algorithm
                sorter = np.argsort(swarm_data)
                swarm_data = swarm_data[sorter]
                point_colors = self.point_colors[i][hue_mask][sorter]

                # Plot the points in centered positions
                try:
                    cat_pos = [self.group_names[i]] * swarm_data.size
                except:
                    cat_pos = np.ones(swarm_data.size) * i
                kws.update(c=point_colors)
                if self.orient == "v":
                    points = ax.scatter(cat_pos, swarm_data, s=s,
                            picker=True,**kws)
                    points.paths = self.paths[i]
                    points.design = self.designs[i]
                else:
                    points = ax.scatter(swarm_data, cat_pos, s=s,
                            picker=True,**kws)
                    points.paths = self.paths[i]
                    points.design = self.designs[i]

                centers.append(self.group_names[i])
                swarms.append(points)

            else:
                offsets = self.hue_offsets
                width = self.nested_width

                for j, hue_level in enumerate(self.hue_names):
                    hue_mask = self.plot_hues[i] == hue_level
                    swarm_data = group_data[hue_mask]

                    # Sort the points for the beeswarm algorithm
                    sorter = np.argsort(swarm_data)
                    swarm_data = swarm_data[sorter]
                    point_colors = self.point_colors[i][hue_mask][sorter]

                    # Plot the points in centered positions
                    center = i + offsets[j]
                    cat_pos = np.ones(swarm_data.size) * center
                    kws.update(c=point_colors)
                    if self.orient == "v":
                        points = ax.scatter(cat_pos, swarm_data, s=s,
                                picker=True,**kws)
                        points.paths = self.paths[i]
                        points.design = self.designs[i]
                    else:
                        points = ax.scatter(swarm_data, cat_pos, s=s,
                                picker=True,**kws)
                        points.paths = self.paths[i]
                        points.design = self.designs[i]

                    centers.append(center)
                    swarms.append(points)

        # Update the position of each point on the categorical axis
        # Do this after plotting so that the numerical axis limits are correct
        for center, swarm in zip(centers, swarms):
            if swarm.get_offsets().size:
               self.swarm_points(ax, swarm, center, width, s, **kws)

    def plot(self, ax, kws):
        """Make the full plot."""
        self.draw_swarmplot(ax, kws)
        self.add_legend_data(ax)
        #self.annotate_axes(ax)
        if self.orient == "h":
            ax.invert_yaxis()

    def _group_longform(self, vals, grouper, order):
        """Group a long-form variable by another with correct order."""
        # Ensure that the groupby will work
        if not isinstance(vals, pd.Series):
            vals = pd.Series(vals)

        # Group the val data
        grouped_vals = self.design._models.groupby(self.x)

        out_data = []
        for g in order:
            try:
                g_vals = pd.DataFrame(grouped_vals.get_group(g))
            except KeyError:
                g_vals = np.array([])

            out_data.append(g_vals)

        # Get the vals axis label
        label = vals.name

        return out_data, label

    @property
    def point_colors(self):
        """Return a color for each scatter point based on group and hue."""
        colors = []
        for i, group_data in enumerate(self.plot_data):

            group_y_data = np.array([y for y in group_data[self.y]])

            # Initialize the array for this group level
            group_colors = np.empty((group_y_data.size, 3))
            print 'group colors',group_colors

            if self.plot_hues is None:

                # Use the same color for all points at this level
                group_color = self.colors[i]
                group_colors[:] = group_color

            else:

                # Color the points based on  the hue level
                for j, level in enumerate(self.hue_names):
                    hue_color = self.colors[j]
                    if group_data.size:
                        group_colors[self.plot_hues[i] == level] = hue_color

            colors.append(group_colors)

        return colors

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
