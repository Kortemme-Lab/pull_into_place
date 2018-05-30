#!/usr/bin/env python2
# encoding: utf-8

"""\

Create a graphic of a tree, each node of which represents a structure,
and each line representing a child-parent relationship. Since the tree
datastructure is inherently very large, visualization requires that the
structures be binned by a metric of interest. 

Usage:
    pull_into_place tree_plot <directory> [<tree_setup_file>] [options]

Options:
    --bin_attribute, -b ATTR
        The attribute to bin structures by. In the future, I plan to
        support binning by different attributes for different levels of
        the tree. 

    --bin_num, -n NUM
        How many bins to split the attribute into. This should also be
        able to be different for each tree level.

"""
from pull_into_place import trees, pipeline
from klab import docopt
import yaml, os



def main():
    args = docopt.docopt(__doc__)

    # Set up workspace & tree

    directory = args['<directory>']
    workspace = pipeline.workspace_from_dir(directory)
    tree = trees.load_tree(workspace)
   
    tree_setup_file = args['<tree_setup_file>']

    with open(tree_setup_file, 'r') as file:
        rules = yaml.load(file)

    print "Setting up tree according to '{0}'.".format(os.path.relpath(tree_setup_file))
    print

    default_rules = {'attribute': 'total_score', 'bins': 20}

    workspace_types = ['RestrainedModels','FixbbDesigns','ValidatedDesigns']
    for ws in workspace_types:
        try:
            sub_rules = rules[1].get(ws, default_rules)
            attribute = sub_rules.get('attribute','total_score')
            bins = sub_rules.get('bins', 20)
        except:
            sub_rules = default_rules
            attribute = sub_rules.get('attribute','total_score')
            bins = sub_rules.get('bins', 20)
        
        list_of_nodes = trees.search_by_records(tree, {'workspace_type': ws, 'round': 1})
        binned_nodes = trees.bin_nodes(list_of_nodes, attribute, bins)
        trees.tree_from_bin_dict(binned_nodes, attribute)

    workspace_types = ['FixbbDesigns', 'ValidatedDesigns']
    for round_num in range(2, workspace.round + 1):
        for ws in workspace_types:
            try:
                sub_rules = rules[round_num].get(ws, default_rules)
                attribute = sub_rules.get('attribute','total_score')
                bins = sub_rules.get('bins', 20)
            except:
                sub_rules = default_rules
                attribute = sub_rules.get('attribute','total_score')
                bins = sub_rules.get('bins', 20)
            
            list_of_nodes = trees.search_by_records(tree, {'workspace_type':\
                ws, 'round': round_num})
            binned_nodes = trees.bin_nodes(list_of_nodes, attribute, bins)
            trees.tree_from_bin_dict(binned_nodes, attribute)

    print tree
    tree.show()
