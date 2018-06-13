#!/usr/bin/env python2
# encoding: utf-8

"""
Create a graphic of a tree, each node of which represents a structure,
and each line representing a child-parent relationship. Since the tree
datastructure is inherently very large, visualization requires that the
structures be binned by a metric of interest. 

Usage:
    pull_into_place tree_plot <directory> <tree_setup_file> [options]

Options:
    --bin_attribute, -a ATTR
        The attribute to bin structures by. In the future, I plan to
        support binning by different attributes for different levels of
        the tree. 

    --nodes_per_bin, -n NUM
        Decide bin_num based on how many nodes you want in each bin (on
        average)

    --bin_num, -b NUM
        Maximum number of bins to split the attribute into. If the
        number of bins as determined by nodes_per_bin is higher than
        this, the number of bins will be set to this number.

    --force, -f
        Force PIP to recalculate the tree.

    --linewidth_all_descendants, -l
        Use this flag to have linewidth be dependant on all descendants
        rather than just the direct children. 

"""
from pull_into_place import trees, pipeline
from klab import docopt
import yaml, os, math
from ete2 import Tree, TreeStyle, NodeStyle, faces, AttrFace, CircleFace

def layout_fn(node):

    if 'bin_attribute' in node.features:
        nstyle = NodeStyle()

        # Set node size based on binned value
        nstyle['shape'] = 'sphere'
        max_metric = max(node.intervals)
        min_metric = min(node.intervals)
        # To do: make the max size ('100') an option. 
        size = 100 * ((max_metric - node.records[node.bin_attribute] )\
            / (max_metric - min_metric))
        #nstyle['size'] = size

        # Set node tree based on # of children
        hzlinewidth = math.ceil(200 * ((float(node.num_children + 1)) /\
            node.max_children))
        vtlinewidth = math.ceil(200 * ((float(len(node.subnodes))) /\
            node.max_subnodes))
        nstyle['vt_line_width'] = hzlinewidth
        nstyle['hz_line_width'] = vtlinewidth

        C = CircleFace(radius=size, color="RoyalBlue", style="sphere")

        faces.add_face_to_node(C, node, 0, position="float")

        node.set_style(nstyle)


def main():
    args = docopt.docopt(__doc__)

    # Set up workspace & tree

    directory = args['<directory>']
    workspace = pipeline.workspace_from_dir(directory)
    force = args['--force']
    direct_children = args['--linewidth_all_descendants']
    tree = trees.load_tree(workspace,force)
   
    tree_setup_file = args['<tree_setup_file>']

    with open(tree_setup_file, 'r') as file:
        rules = yaml.load(file)

    print "Setting up tree according to '{0}'.".format(os.path.relpath(tree_setup_file))
    print
    print

    attribute = args['--bin_attribute']
    bin_num = args['--bin_num']
    nodes_per_bin = args['--nodes_per_bin']
    
    user_defaults = {'attribute':attribute, 'bins':bin_num,
            'nodes_per_bin':nodes_per_bin}

    trees.construct_binned_tree(tree, rules, user_defaults,
            not direct_children)
    print 

    style = TreeStyle()
    style.mode = 'c'
    style.arc_start = -180
    style.arc_span = 180
    style.show_leaf_name = False
    style.layout_fn = layout_fn

    max_children = 0.0
    max_subnodes = 0.0
    for node in tree.iter_descendants():
        if node.num_children > max_children:
            max_children = float(node.num_children)
        if len(node.subnodes) > max_subnodes:
            max_subnodes = float(len(node.subnodes))
    # Annoyingly, we have to add max_children to all nodes in order to
    # use it in the layout function. 
    root_children = 0.0
    for node in tree.iter_descendants():
        node.add_features(max_children = max_children, max_subnodes =
                max_subnodes)
    
    nstyle = NodeStyle()
    nstyle['size'] = 100
    nstyle['vt_line_width'] = 50
    nstyle['hz_line_width'] = 50

    tree.set_style(nstyle)
    tree.show(tree_style = style)

