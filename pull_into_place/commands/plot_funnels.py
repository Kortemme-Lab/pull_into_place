#!/usr/bin/env python2
# encoding: utf-8

"""\
Visualize the results from the loop modeling simulations in PIP and identify 
promising designs.

Usage:
    pull_into_place plot_funnels <pdb_directories>... [options]

Options:
    -F, --no-fork
        Do not fork into a background process.

    -f, --force
        Force the cache to be regenerated.

    -q, --quiet
        Build the cache, but don't launch the GUI.

This command launches a GUI designed to visualize the results for the loop 
modeling simulations in PIP and to help you identify promising designs.  To 
this end, the following features are supported:

1. Extract quality metrics from forward-folded models and plot them against 
   each other in any combination.

2. Easily visualize specific models by right-clicking on plotted points.  
   Add your own visualizations by writing `*.sho' scripts.

3. Plot multiple designs at once, for comparison purposes.

4. Keep notes on each design, and search your notes to find the designs you 
   want to visualize.

Generally, the only arguments you need are the names of one or more directories 
containing the PDB files you want to look at.  For example:

    $ ls -R
    .:
    design_1  design_2 ...

    ./design_1:
    model_1.pdb  model_2.pdb ...

    ./design_2:
    model_1.pdb  model_2.pdb ...

    $ pull_into_place plot_funnels design_*

This last command will launch the GUI.  If you specified more than one design 
on the command line, the GUI will have a panel on the left listing all the 
designs being compared.  You can control what is plotted by selecting one or 
more designs from this list.  The search bar at the top of this panel can be 
used to filter the list for designs that have the search term in their 
descriptions.  The buttons at the bottom can be used to save information about 
whatever designs are selected.  The "Save selected paths" button will save a 
text file listing the path to the lowest scoring model for each selected 
design.  The "Save selected funnels" button will save a PDF with the plot for 
each selected design on a separate page.

The upper right area of the GUI will contain a plot with different metrics on 
the two axes where each point represents a single model.  You can right-click 
on any point to take an action on the model represented by that point.  Usually 
this means visualizing the model in an external program, like pymol or chimera.  
You can also run custom code by writing a script with the extension *.sho that 
takes the path of a model as its only argument.  ``plot_funnels`` will search 
for scripts with this extension in every directory starting with the directory 
containing the model in question and going down all the way to the root of the 
file system.  Any scripts that are found are added to the menu you get by 
right-clicking on a point, using simple rules (the first letter is capitalized 
and underscores are converted to spaces) to convert the file name into a menu 
item name.

The tool bar below the plot can be used to pan around, zoom in or out, save an 
image of the plot, or change the axes.  If the mouse is over the plot, its 
coordinates will be shown just to the right of these controls.  Below the plot 
is a text form which can be used to enter a description of the design.  These 
descriptions can be searched.  I like using the '+', '++', ... convention to 
rank designs so I can easily search for increasingly good designs.

Hotkeys:
    j,f,down: Select the next design, if there is one.
    k,d,up: Select the previous design, if there is one.
    i,a: Focus on the description form.
    z: Use the mouse to zoom on a rectangle.
    x: Use the mouse to pan (left-click) or zoom (right-click).
    c: Return to the original plot view.
    slash: Focus on the search bar.
    tab: Change the y-axis metric.
    space: Change the x-axis metric.
    escape: Unfocus the search and description forms.
"""

import os, glob, numpy as np
from .. import pipeline, structures

def main():
    import docopt
    args = docopt.docopt(__doc__)

    # Defer trying to use PyGTK (which will happen when ``show_my_designs`` is 
    # imported) until after ``docopt`` has had a chance to print the help 
    # message.  This was a problem because ReadTheDocs needs to run this 
    # command with the help flag to generate the command usage page, but PyGTK 
    # can't be installed with pip.

    import show_my_designs as smd

    class PipDesign (smd.Design):

        def _load_models(self, use_cache):
            self._models = structures.load(
                    self.directory,
                    use_cache=use_cache,
                    require_io_dir=False,
            )


    smd.Design = PipDesign

    smd.default_x_metric = 'restraint_dist'
    smd.default_y_metric = 'total_score'

    smd.metric_titles['total_score'] = u"Total Score (REU)"
    smd.metric_titles['dunbrack_score'] = u"Dunbrack Score (REU)"
    smd.metric_titles['buried_unsat_score'] = u"Δ Buried Unsats"
    smd.metric_titles['restraint_dist'] = u"Restraint Satisfaction (Å)"
    smd.metric_titles['loop_dist'] = u"Loop RMSD (Å)"

    smd.metric_limits['total_score'] = lambda x: (min(x), np.percentile(x, 85))
    smd.metric_limits['restraint_dist'] = lambda x: (0, np.percentile(x, 95))
    smd.metric_limits['loop_dist'] = lambda x: (0, np.percentile(x, 95))

    smd.metric_guides['restraint_dist'] = 1.0
    smd.metric_guides['loop_dist'] = 1.0

    smd.show_my_designs(
            args['<pdb_directories>'],
            use_cache=not args['--force'],
            launch_gui=not args['--quiet'],
            fork_gui=not args['--no-fork'],
    )
