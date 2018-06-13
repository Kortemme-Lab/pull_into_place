from . import pipeline, structures
from ete2 import Tree
import glob, os, pickle, math
from sys import stdout

"""
This file defines functions needed for tree construction and
manipulation. 
(TO DO: Refactor this code into a class so that things like the initial
workspace, the bin dictionary, intervals dictionary, etc. can be shared
between functions. This might not work, though, since each bin can have
different intervals, etc... and we want to make sure the correct
lists/dictionaries are being used for each function.)
"""

def cluster_nodes_by_coords(list_of_nodes):
    """
    pseudo-code:
    dist_matrix = np.zeros((len(list_of_nodes),len(list_of_nods)))
    structures = [node.records for node in list_of_nodes]
    Note that we can edit the structures in the list and it will edit
    the node.records dict (it's a list of pointers to the node.records
    dicts)
    structure combos = itertools.combinations(enumerate(structures),2)
    
    for (i, structure_i), (j_structure_j) in structure_combos:
        dist_matrix[i,j] = calculate_loop_rmsd(structure_i,structure_j)
        dist_matrix[j,i] = dist_matrix[i,j]

    dist_vector = sp_dist..squareform(dist_matrix)
    mean_dist = np.mean(dist_vector)
    hierarchy = sp_clust.complete(dist_vector)
    clusters = sp_clust.fcluster(hierarchy, threshold or mean_dist,
    criterion='distance')

    for cluster, design in zip(clusters, designs):
        structure.structure_cluster = cluster

    """

def load_tree(bigjobworkspace, force=False):
    """
    Returns a cached tree if available, otherwise calculates one. 
    """

    tree_path = bigjobworkspace.tree_path
    if os.path.exists(tree_path) and not force:
        print "Found cached tree. Loading..."
        with open(tree_path,'r') as file:
            tree = pickle.load(file)
    else:
        tree = create_full_tree(bigjobworkspace)
        with open(tree_path,'w') as file:
            pickle.dump(tree,file)

    return tree

def create_shallow_trees(workspace):
    """
    Returns a list of nodes. Each node represents a structure, with
    child nodes representing all the structures that used the parent
    node as an input. 
    """

    shallow_trees = []

    for folder in workspace.output_subdirs:
        design = structures.Design(folder)
        data = design.structures.to_dict('records')
        parent_paths = {}
        for structure in data:
            structure['full_path'] = os.path.join(folder,structure['path'])
            structure['workspace_type'] = str(type(workspace)).split('.')[-1].split('\'')[0]
            structure['round'] = workspace.round
            parent_path = workspace.parent(structure['full_path'])

            if parent_path in parent_paths:
                parent_paths[parent_path].append(structure)
            else:
                parent_paths[parent_path] = [structure]
        for path in parent_paths:
            node = Tree()
            node.name = path
            for structure in parent_paths[path]:
                # Add children and annotate them with records dictionary
                child = node.add_child(name=structure['full_path'])
                child.add_features(records=structure)
            shallow_trees.append(node)

    return shallow_trees

def combine_trees(list_of_child_trees, list_of_parent_trees):
    """
    Take two shallow trees and combine them; attach nodes with
    identical names to each other, then delete the (non-annotated)
    child node (its children will automatically be attached to the
    parent node).  
    """

    for new_tree in list_of_parent_trees:
        for node in new_tree:
            for child_tree in list_of_child_trees:
                if node.name == child_tree.name:
                    node.add_child(child_tree)
                    child_tree.delete()

def create_full_tree(bigjobworkspace, child_trees = [], recurse = True):
    """
    Creates a tree datastructure going backwards from the given
    workspace. This tree will contain all structures and will be very
    large - not useful for direct visualization, but is meant to be used to
    create graphs whose axes span different steps in the pipeline.
    child_trees is list of trees from a previous iteration (or an
    empty list).
    """

    print "Creating nodes for ", bigjobworkspace.output_dir
    try:
        bigjobworkspace.predecessor
        recurse = True
    except:
        recurse = False

    if recurse:
        parent_trees = create_shallow_trees(bigjobworkspace)
        combine_trees(child_trees, parent_trees)
        return create_full_tree(bigjobworkspace.predecessor, parent_trees, recurse)

    parent_trees = create_shallow_trees(bigjobworkspace)
    combine_trees(child_trees, parent_trees)


    return parent_trees[0]

def search_by_records(tree, desired_attributes_dict, use_and=True):
    """
    Finds nodes of a given tree that match a dictionary of attributes
    whose key:value pairs represent an attribute of 'records' and the
    desired value. Matches must match all attributes in dictionary by
    default, but if use_and is set to False then it's treated as an
    'or' statement. 
    """
    
    matches = []

    for node in tree.iter_descendants():
        match = use_and
        if use_and:
            for key in desired_attributes_dict:
                if node.records[key] != desired_attributes_dict[key]:
                    match = False
        else:
            for key in desired_attributes_dict:
                if node.records[key] == desired_attributes_dict[key]:
                    match = True
        if match == True:
            matches.append(node)

    return matches

def tree_from_bin_dict(binned_nodes, attribute, intervals,
        direct_children = True):
    """
    Using a binned nodes dictionary taken from bin_nodes() function,
    reshape the tree so that a representative node replaces all other
    nodes in that bin. 
    """


    # Note that the intervals list is being passed into this function
    # because otherwise it would be very difficult to find the min and
    # max intervals for plotting later. We need to attach them to each
    # node, since different nodes might have different binning rules. 

    for category in binned_nodes:
        for interval_floor in binned_nodes[category]:
            representative = Tree()
            intervals.append(interval_floor)
            lowest_att = binned_nodes[category][interval_floor][0]
            for node in binned_nodes[category][interval_floor]:
                # Need to iterate through once to find
                # representative node
                if node.records[attribute] < lowest_att:
                    representative = node
                    lowest_att = node.records[attribute]
            representative.add_features(subnodes = [], bin_attribute =\
                    attribute, intervals = intervals)
            if direct_children:
                num_children = len(representative.children)
            else:
                num_children = 0
                for child in representative.iter_descendants():
                    num_children += 1
            for node in binned_nodes[category][interval_floor]:
                # Second iteration to reshape the tree
                if node != representative:
                    if direct_children:
                        num_children += len(node.children)
                    else:
                        for child in node.iter_descendants():
                            num_children += 1
                    for child in node.children:
                        representative.add_child(child)
                        representative.subnodes.append(child.records)
                    node.detach()
            representative.add_features(num_children = num_children)

def bin_nodes(list_of_nodes, attribute, num_bins, combine_with_leaves=False,
        discard_nodes_missing_data=True):
    """
    Takes a list of nodes and bins them according to attribute (must be
    a numbered attribute) and num_bins. Returns a dictionary which
    contains either 1 or 2 dictionaries, depending on whether    
    combine_with_leaves is True or False; if False, internal nodes and
    leaves are separated before binning. If True, all nodes are
    combined. 

    Each category then contains a dictionary whose keys are numbers
    representing the lower bound of the bin. Those keys each point to a
    list of nodes. 
    
    The returned dictionary thus has the following format:

    binned_nodes = { 'nodes':{-1413:[<nodes>], -1418:[<nodes>], ... },
    'leaves':{<empty if combine_with_leaves = True, otherwise looks like
    the 'nodes' diectionary>} }
    """

    data = []
    for node in list_of_nodes:
        # We first need to get all the raw data. Unfortunately this
        # means iterating through the list of nodes twice.
        data.append(node.records[attribute])

    interval = ( float(max(data)) - float(min(data)) ) / float(num_bins)
    intervals = []
    i = min(data)
    while i <= max(data):
        intervals.append(i)
        i += interval
    intervals.append(i)

    # Split the nodes into those with children and without children if
    # combine_with_leaves==False. 

    interesting_nodes = {}
    interesting_nodes['nodes'] = []
    if not combine_with_leaves:
        interesting_nodes['leaves'] = []
        for node in list_of_nodes:
            if node.children:
                interesting_nodes['nodes'].append(node)
            else:
                interesting_nodes['leaves'].append(node)
    else:
        interesting_nodes['nodes'] = list_of_nodes

    binned_nodes = {}

    num_nodes = len(list_of_nodes)
    data_min = min(data)

    for category in interesting_nodes:
        binned_nodes[category] = {}
        for index, node in enumerate(interesting_nodes[category]):
            stdout.write("\rBinning node {} of {}".format(index,num_nodes))
            stdout.flush()
            bin_index = int(math.floor((node.records[attribute] -\
                    data_min ) / interval))
            if bin_index == len(intervals) - 1:
                # Unfortunately we need to slightly over-weight the
                # highest category (could also be the lowest category if
                # we wanted) by making it inclusive on both ends.
                # Otherwise, the highest value would always be in a
                # category by itself. 
                bin_index = bin_index - 1

            if intervals[bin_index] in binned_nodes[category]:
                binned_nodes[category][intervals[bin_index]].append(node) 
            else:
                binned_nodes[category][intervals[bin_index]] = [node]

    return binned_nodes, intervals

def construct_binned_tree(tree, rules, user_defaults = {},
        direct_children=True):
    """
    Alter the tree according to binning rules.
    """

    get_rules = tree.children[0]
    workspace_type = get_rules.records['workspace_type']
    round_number = get_rules.records['round']

    for child in tree.children:
        assert(child.records['workspace_type'] == workspace_type and
                child.records['round'] == round_number), \
                        'Something went wrong with constructing the binned tree.'

    default_rules = {'attribute': 'total_score', 'nodes_per_bin': 2000}
    # User defaults override built-in defaults
    for key in user_defaults:
        if user_defaults[key]:
            default_rules[key] = user_defaults[key]


    CURSOR_UP_ONE = '\x1b[1A' 
    ERASE_LINE = '\x1b[2K'
    stdout.write(CURSOR_UP_ONE + ERASE_LINE + '\rBinning nodes for ' + workspace_type + ' round ' +\
            str(round_number) + '\r\n')
    stdout.flush()

    try:
        sub_rules = rules[round_number].get(workspace_type, default_rules)
    except:
        sub_rules = default_rules

    # Apply default rules when user-defined subrules don't specify
    for key in default_rules:
        if key not in sub_rules:
            sub_rules[key] = default_rules[key]

    attribute = sub_rules.get('attribute','total_score')

    # Figure out how many bins to use.
    bins = int(math.ceil(float(len(tree.children)) /\
            float(sub_rules.get('nodes_per_bin'))))
    if 'bins' in sub_rules:
        max_bins = sub_rules.get('bins')
    else:
        max_bins = user_defaults.get('bins')
    if max_bins:
        if bins > int(max_bins):
            bins = int(max_bins)


    binned_nodes, intervals = bin_nodes(tree.children, attribute,\
            bins)
    tree_from_bin_dict(binned_nodes, attribute, intervals,
            direct_children)

    for child in tree.children:
        if child.children:
            construct_binned_tree(child, rules,\
                    user_defaults, direct_children)
