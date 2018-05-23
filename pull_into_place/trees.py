from . import pipeline, structures
from ete2 import Tree
import glob, os

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
            try:
                structure['round'] = workspace.round
            except:
                structure['round'] = 0
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
    large - not useful for visualization. 
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

    root = Tree(name=bigjobworkspace.input_pdb_path)
    for tree in child_trees:
        root.add_child(tree)
        tree.delete()
    return root

def search_by_records(tree, desired_attributes_dict, exclusive=True):
    """
    Finds nodes of a given tree that match a dictionary of attributes
    whose key:value pairs represent an attribute of 'records' and the
    desired value. Matches must match all attributes in dictionary by
    default, but if exlusive is set to False then it's treated as an
    'or' statement. 
    """
    
    matches = []

    for node in tree.iter_descendants():
        match = exclusive
        if exclusive:
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
