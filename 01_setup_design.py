#!/usr/bin/env python2

"""\
Query the user for all the input data needed for a design.  This includes a 
starting PDB file, the backbone regions that will be remodeled, the residues 
that will be allowed to design, and more.  A brief description of each field is 
given below.  This information is used to build a directory for this design 
that will be used by the rest of the scripts in this pipeline.  

Usage: 01_setup_design.py <name>
"""

keys = (   # (fold)
        'input_pdb',
        'loops_path',
        'resfile_path',
        'flags_path',
        'restraints_path',
        #'cluster_path',
        'rosetta_path',
)

prompts = {   # (fold)
        'input_pdb': "Path to the input PDB file: ",
        'loops_path': "Path to the loops file: ",
        'resfile_path': "Path to resfile: ",
        'flags_path': "Path to flags file: ",
        'restraints_path': "Path to restraints file: ",
        'cluster_path': "Path to project on cluster: ",
        'rosetta_path': "Path to rosetta: ",
}
descriptions = {   # (fold)
        'input_pdb': """\
Input PDB file: A structure containing the functional groups to be positioned.  
This file should already be parse-able by rosetta, which often means it must be 
stripped of waters and miscellaneous ions.""",

        'loops_path': """\
Loops file: A file specifying which backbone regions will be allowed to move.  
These backbone regions do not have to be contiguous, but each region must span 
at least 4 residues.""",

        'resfile_path': """\
Resfile: A file specifying which positions to design and which positions to 
repack.  I recommend designing as few residues as possible outside the loops.""",

        'flags_path': """\
Flags file: A file containing command line flags that should be passed to every 
invocation of rosetta for this design.  For example, if your design involves a 
ligand, put flags related to the ligand parameter files in this file.""",

        'restraints_path': """\
Restraints file: A file describing the geometry you're trying to design.  In 
rosetta parlance, this is more often (inaccurately) called a constraint file.  
Note that restraints are only used to build the initial set of models.""",

        'cluster_path': """\
Cluster checkout: The path to your project files on the cluster.  This setting 
is used to keep the two locations in sync.""",

        'rosetta_path': """\
Rosetta checkout: Rosetta is used both locally and on the cluster.  Because 
paths are often different between machines, this setting is not copied to the 
cluster.  Instead, you must manually specify it by making a symlink called 
rosetta in the design directory.""",
}


if __name__ == '__main__':
    try:
        import os, readline
        from libraries import docopt
        from libraries import files

        help = __doc__ + '\n' + '\n\n'.join(descriptions[x] for x in keys)
        arguments = docopt.docopt(help)
        design = files.Design(arguments['<name>'])

        # Make sure this design doesn't already exist.

        if design.exists():
            print "Design '{0}' already exists.  Aborting.".format(design.name)
            raise SystemExit

        # Get the necessary paths from the user.

        print "Please provide the following pieces of information:"
        print

        settings = {}
        readline.parse_and_bind("tab: complete")
        prompt = lambda key: os.path.expanduser(raw_input(prompts[key]))

        for key in keys:
            print descriptions[key]
            print
            settings[key] = prompt(key)
            while not os.path.exists(settings[key]):
                print "'{0}' does not exist.".format(settings[key])
                print
                settings[key] = prompt(key)
            print

        # Fill in the design directory.
        
        os.makedirs(design.root_path)

        def make_link(source, target):
            if not source.startswith('/'):
                source = os.path.join(design.inverse_path, source)
            os.symlink(source, target)

        make_link(settings['input_pdb'], design.input_pdb_path)
        make_link(settings['loops_path'], design.loops_path)
        make_link(settings['resfile_path'], design.resfile_path)
        make_link(settings['flags_path'], design.flags_path)
        make_link(settings['restraints_path'], design.restraints_path)
        make_link(settings['rosetta_path'], design.rosetta_path)

        print "Setup successful for design '{0}'.".format(design.name)

    except KeyboardInterrupt:
        print

