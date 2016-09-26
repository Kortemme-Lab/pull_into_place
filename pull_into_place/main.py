#!/usr/bin/env python2

"""\
Pull Into Place (PIP) is a protocol to design protein functional groups with 
sub-angstrom accuracy.  The protocol is based on two ideas: 1) using restraints 
to define the geometry you're trying to design and 2) using an unrestrained 
simulations to test designs.

Usage:
    pull_into_place <command> [<args>...]
    pull_into_place --version
    pull_into_place --help

Arguments:
    <command>
        The name of the command you want to run.  You only need to specify 
        enough of the name to be unique.  Broadly speaking, there are two 
        categories of scripts.  The first are part of the main design pipeline.  
        These are prefixed with numbers so that you know the order to run them 
        in.  The second are helper scripts and are not prefixed.

{command_table}

    <args>...
        The necessary arguments depend on the command being run.  For more 
        information, pass the '--help' flag to the command you want to run.

Options:
    -v, --version
        Display the version of PIP that's installed.

    -h, --help
        Display this help message.

PIP's design pipeline has the following steps:

1. Define your project.  This entails creating an input PDB file and preparing 
   it for use with rosetta, creating a restraints file that specifies your 
   desired geometry, creating a resfile that specifies which residues are 
   allowed to design, and creating a loop file that specifies where backbone 
   flexibility will be considered.

   $ pull_into_place 01_setup_workspace ...

2. Build a large number of models that plausibly support your desired geometry 
   by running flexible backbone Monte Carlo simulations restrained to stay near 
   said geometry.  The goal is to find a balance between finding models that 
   are realistic and that satisfy your restraints.

   $ pull_into_place 02_setup_model_fragments ...
   $ pull_into_place 03_build_models ...

3. Filter out models that don't meet your quality criteria.

   $ pull_into_place 04_pick_models_to_design ...

4. Generate a number of designs for each model remaining.

   $ pull_into_place 05_design_models ...

5. Pick a small number of designs to validate.  Typically I generate 100,000 
   designs and can only validate 50-100.  I've found that randomly picking 
   designs according to the Boltzmann weight of their rosetta score gives a 
   nice mix of designs that are good but not too homogeneous.

   $ pull_into_place 06_pick_designs_to_validate ...

6. Validate the designs using unrestrained Monte Carlo simulations.  Designs 
   that are "successful" will have a funnel on the left side of their score vs 
   rmsd plots.

   $ pull_into_place 07_setup_design_fragments ...
   $ pull_into_place 08_validate_designs ...

7. Optionally take the decoys with the best geometry from the validation run 
   (even if they didn't score well) and feed them back into step 3.  Second and 
   third rounds of simulation usually produce much better results than the 
   first, because the models being designed are more realistic.  Additional 
   rounds of simulation give diminishing returns, and may be more effected by 
   some of rosetta's pathologies (i.e. it's preference for aromatic residues).

   $ pull_into_place 04_pick_models_to_design ...
   $ pull_into_place 05_design_models ...
   $ pull_into_place 06_pick_designs_to_validate ...
   $ pull_into_place 07_setup_design_fragments ...
   $ pull_into_place 08_validate_designs ...

8. Generate a report summarizing a variety of quality metrics for each design.  
   This report is meant to help you pick designs to test experimentally.

   $ pull_into_place 09_compare_best_designs ...
"""

import sys, re
from klab import docopt, scripting
from . import __version__

def make_command_table(entry_points):
    """
    Return a nicely formatted table of all the PIP commands installed on this 
    system to incorporate into the help text.  The table will have two columns.  
    The first will list the commands that comprise the main pipeline and the 
    second will list all the other miscellaneous helper functions.
    """
    import itertools

    # Split every command installed on the system into two categories: those 
    # that are part of the main pipeline and those that are just utilities or 
    # helpers.  Pipeline scripts start with numbers, helper scripts don't.

    pipeline_commands = []
    helper_commands = []

    for command in sorted(entry_points):
        if re.match('\d+_', command):
            pipeline_commands.append(command)
        else:
            helper_commands.append(command)

    # Figure out what the longest pipeline command is, so we know how much to 
    # indent the helper commands.

    longest_pipeline_command = 0
    for command in pipeline_commands:
        longest_pipeline_command = max(len(command), longest_pipeline_command)

    # Make the table.

    rows = []
    columns = itertools.izip_longest(
            pipeline_commands, helper_commands, fillvalue='')

    for commands in columns:
        row = '        {0[0]:{1}}   {0[1]}'.format(
                commands, longest_pipeline_command)
        rows.append(row)

    return '\n'.join(rows)

def did_you_mean(unknown_command, entry_points):
    """
    Return the command with the name most similar to what the user typed.  This 
    is used to suggest a correct command when the user types an illegal 
    command.
    """
    from difflib import SequenceMatcher
    similarity = lambda x: SequenceMatcher(None, x, unknown_command).ratio()
    did_you_mean = sorted(entry_points, key=similarity, reverse=True)
    return did_you_mean[0]

@scripting.catch_and_print_errors()
def main():
    from pkg_resources import iter_entry_points, DistributionNotFound

    # Load every PIP command installed on this system.  This is cool because by 
    # using ``pkg_resources``, other packages can add commands to PIP!
    entry_points = {}
    for entry_point in iter_entry_points(group='pull_into_place.commands'):
        entry_points[entry_point.name] = entry_point

    # Read the command the user typed on the command line.
    command_table = make_command_table(entry_points)
    arguments = docopt.docopt(
            __doc__.format(**locals()),
            version=__version__,
            options_first=True,
    )
    command_name = arguments['<command>']

    # Find all the commands that match what the user typed.
    matching_entry_points = [
            name for name in entry_points
            if name.startswith(command_name)]

    # If no commands match, print out an error and suggest a command the user 
    # might have been trying to type.
    if len(matching_entry_points) == 0:
        scripting.print_error_and_die("""\
Unknown command '{0}'.  Did you mean:

    $ pull_into_place {1} {2}

""", command_name, did_you_mean(command_name, entry_points), ' '.join(arguments['<args>']))

    # If two or more commands match, print all the ambiguous commands and tell 
    # the user to be more specific.
    elif len(matching_entry_points) > 1:
        message = "Command '{0}' is ambiguous.  Did you mean:\n\n"
        for matching_entry_point in matching_entry_points:
            message += "    $ pull_into_place {0} {{1}}\n".format(matching_entry_point)
        message += '\n'
        scripting.print_error_and_die(message, command_name, ' '.join(arguments['<args>']))

    # If a unique command was given, make sure all of its dependencies are 
    # installed (because the dependencies for the analysis scripts are not by 
    # default).  If there is a problem, suggest how to fix it.  Otherwise, run 
    # the command.
    else:
        entry_point = entry_points[matching_entry_points[0]]

        try:
            entry_point.require()
        except DistributionNotFound as error:
            scripting.print_error_and_die("""\
The '{0}' command requires the '{1.req}' package.

The analysis scripts have a number of dependencies that aren't installed by 
default, because they would make PIP needlessly hard to install on clusters.  
You can install all of these dependencies at once with the following command:

    $ pip install 'pull_into_place [analysis]'

""".format(command_name, error))

        sys.argv = sys.argv[:1] + matching_entry_points + arguments['<args>']
        entry_point.load()()
