#!/usr/bin/env python2

"""\
This module defines the Workspace classes that are central to every script.
The role of these classes is to provide paths to all the data files used in any
part of the pipeline and to hide the organization of the directories containing
those files.  The base Workspace class deals with files in the root directory
of a design.  It's subclasses deal with file in the different subdirectories of
the design, each of which is related to a cluster job.
"""

import os, re, glob, json, pickle
from klab import scripting
from pprint import pprint

class Workspace(object):
    """
    Provide paths to every file used in the design pipeline.

    Each workspace object is responsible for returning paths to files that are
    relevant to a particular stage of the design pipeline.  These files are
    organized hierarchically: files that are relevant to many parts of the
    pipeline are stored in the root design directory while files that are
    relevant to specific stages are stored in subdirectories.  You can think of
    each workspace class as representing a different directory.

    The Workspace class itself represents the root directory, but it is also
    the superclass from which all of the other workspace derive.  The reason
    for this is that the root workspace knows where all the shared parameter
    files are located, and this information is needed in every workspace.

    When modifying or inheriting from this class, keep in mind two things.
    First, workspace objects should do little more than return paths to files.
    There are a few convenience functions that clear directories and things
    like that, but these are the exception rather than the rule.  Second, use
    the @property decorator very liberally to keep the code that uses this API
    succinct and easy to read.
    """

    def __init__(self, root):
        self._root_dir = os.path.abspath(root)

    @classmethod
    def from_directory(cls, directory):
        # Force subclasses to reimplement this method
        if cls != Workspace:
            raise NotImplementedError

        return Workspace(directory)

    @property
    def parent_dir(self):
        return os.path.dirname(self.root_dir)

    @property
    def root_dir(self):
        return self._root_dir

    @property
    def abs_root_dir(self):
        return os.path.abspath(self.root_dir)

    @property
    def focus_name(self):
        """
        The "name" of the directory managed by this class, e.g. for finding 
        input files.  This is meant to be overridden in subclasses.
        """
        return ''

    @property
    def focus_dir(self):
        """
        The particular directory managed by this class.  This is meant to be
        overridden in subclasses.
        """
        return self.root_dir

    @property
    def standard_params_dir(self):
        return os.path.join(self.root_dir, 'standard_params')

    @property
    def project_params_dir(self):
        return os.path.join(self.root_dir, 'project_params')

    @property
    def seqprof_dir(self):
        return os.path.join(self.focus_dir, 'sequence_profiles')

    @property
    def fragment_weights_path(self):
        return self.find_path('fragment.wts')

    @property
    def io_dirs(self):
        return []

    @property
    def filters_list(self):
        return os.path.join(self.root_dir, 'filters.yaml')

    @property
    def rosetta_dir(self):
        return self.find_path('rosetta', self.root_dir)

    @property
    def rosetta_scripts_path(self):
        pattern = self.rosetta_subpath('source', 'bin', 'rosetta_scripts*')
        executables = glob.glob(pattern)

        # Sometimes dead symlinks end up in the `bin/` directory, so explicitly
        # ignore those.

        executables = [x for x in executables if os.path.exists(x)]

        # Print a (hopefully) helpful error message if no ``rosetta_scripts``
        # executables are found.

        if len(executables) == 0:
            raise PipelineError("""\
No RosettaScripts executable found.

Expected to find a file matching '{0}'.  Did you forget to compile rosetta?
""".format(pattern))

        # Sort the ``rosetta_scripts`` executables such that those containing
        # the word 'release' end up at the front of the list, those containing
        # 'debug' end up at the back, and shorter file names (which have fewer
        # weird compilation options) end up in front of longer ones.  We'll
        # ultimately pick the first path in the list, so we're doing our best
        # to use a basic release mode executable.

        executables.sort(key=lambda x: len(x))
        executables.sort(key=lambda x: 'debug' in x)
        executables.sort(key=lambda x: 'release' not in x)

        return executables[0]

    @property
    def rosetta_database_path(self):
        return self.rosetta_subpath('database')

    def rosetta_vall_path(self, test_run=False):
        return os.path.join(self.rosetta_database_path, 'sampling',
                'small.vall.gz' if test_run else 'vall.jul19.2011.gz')

    def rosetta_subpath(self, *subpaths):
        return os.path.join(self.rosetta_dir, *subpaths)

    @property
    def input_pdb_path(self):
        return self.find_path('input.pdb.gz')

    @property
    def loops_path(self):
        return self.find_path('loops')

    @property
    def loop_segments(self):
        return load_loops(self.root_dir,self.loops_path)

    @property
    def largest_loop(self):
        """
        Return the boundaries for the largest loop segment.
        
        This is just meant to be a reasonable default for various selectors and 
        filters to work with, in the case that more than one loop is being 
        modeled.  If you want to be more precise, you'll have to override the 
        selectors and filters in question.
        """
        from collections import namedtuple
        Loop = namedtuple('Loop', 'start end')
        largest_segment = sorted(
                self.loop_segments,
                key=lambda x: abs(x[1] - x[0]),
        )[-1]
        return Loop(*largest_segment)

    @property
    def resfile_path(self):
        return self.find_path('resfile')

    @property
    def restraints_path(self):
        return self.find_path('restraints')

    @property
    def scorefxn_path(self):
        return self.find_path('scorefxn.wts')

    @property
    def filters_path(self):
        return self.find_path('filters.xml')

    @property
    def pick_file(self):
        return self.find_path('picks.yml')

    @property
    def metrics_dir(self):
        return self.find_path('metrics')

    @property
    def metric_scripts(self):
        return glob.glob(os.path.join(self.metrics_dir, '*'))

    @property
    def build_script_path(self):
        return self.find_path('build_models.xml')

    @property
    def design_script_path(self):
        return self.find_path('design_models.xml')

    @property
    def validate_script_path(self):
        return self.find_path('validate_designs.xml')

    @property
    def shared_defs_path(self):
        return self.find_path('shared_defs.xml')

    @property
    def flags_path(self):
        return self.find_path('flags')

    @property
    def rsync_url_path(self):
        return self.find_path('rsync_url')

    @property
    def rsync_url(self):
        if not os.path.exists(self.rsync_url_path):
            raise UnspecifiedRemoteHost()
        with open(self.rsync_url_path) as file:
            return file.read().strip()

    @property
    def rsync_recursive_flag(self):
        return False

    @property
    def rsync_include_patterns(self):
        return []

    @property
    def rsync_exclude_patterns(self):
        return ['rosetta', 'rsync_url']

    @property
    def preferred_install_dir(self):
        return os.path.join(self.project_params_dir, self.focus_name)

    @property
    def find_path_dirs(self):
        # The search path has to be a little different for the root directory, 
        # otherwise you end up with some weird behavior dues to the focus 
        # directory (which is the first place to look for files) being the same 
        # as the root directory (which is the last place to look for files).

        if self.focus_dir == self.root_dir:
            return [
                    self.root_dir,
                    self.project_params_dir,
                    self.standard_params_dir,
            ]
        else:
            return [
                    self.focus_dir,
                    os.path.join(self.root_dir, self.focus_name),
                    os.path.join(self.project_params_dir, self.focus_name),
                    self.root_dir,
                    self.project_params_dir,
                    os.path.join(self.standard_params_dir, self.focus_name),
                    self.standard_params_dir,
            ]

    def find_path(self, basename, install_dir=None):
        """
        Look in a few places for a file with the given name.  If a custom
        version of the file is found in the directory being managed by
        this workspace, return it.  Otherwise look in the custom and default 
        input directories in the root directory, and then finally in the root 
        directory itself.

        This function makes it easy to provide custom parameters to any stage
        to the design pipeline.  Just place the file with the custom parameters
        in a directory associated with that stage.
        """

        # Look for the file we were asked for.
        for dir in self.find_path_dirs:
            path = os.path.join(dir, basename)
            if os.path.exists(path):
                return path

        # If we didn't find the file, return the path to where we'd like it to 
        # be installed.
        return os.path.join(install_dir or self.preferred_install_dir, basename)

    def check_paths(self):
        required_paths = [
                self.input_pdb_path,
                self.loops_path,
                self.resfile_path,
                self.restraints_path,
                self.build_script_path,
                self.design_script_path,
                self.validate_script_path,
                self.flags_path,
        ]
        for path in required_paths:
            if not os.path.exists(path):
                raise PathNotFound(path)

    def check_rosetta(self):
        required_paths = [
                self.rosetta_database_path,
                self.rosetta_scripts_path,
                self.rosetta_vall_path(False),
                self.rosetta_vall_path(True),
        ]
        for path in required_paths:
            if not os.path.exists(path):
                raise PathNotFound(path)

    @property
    def incompatible_with_fragments_script(self):
        return re.search('[^a-zA-Z0-9_/.]', self.abs_root_dir)

    def make_dirs(self):
        scripting.mkdir(self.focus_dir)

        pickle_path = os.path.join(self.focus_dir, 'workspace.pkl')
        with open(pickle_path, 'w') as file:
            pickle.dump(self.__class__, file)

    def cd(self, *subpaths):
        """
        Change the current working directory and update all the paths in the
        workspace.  This is useful for commands that have to be run from a
        certain directory.
        """
        target = os.path.join(*subpaths)
        os.chdir(target)

    def cd_to_root(self):
        self.cd(self.root_dir)

    def exists(self):
        return os.path.exists(self.focus_dir)


class BigJobWorkspace(Workspace):
    """
    Provide paths needed to run big jobs on the cluster.

    This is a base class for all the workspaces meant to store results from
    long simulations (which is presently all of them except for the root).
    This class provides paths to input directories, output directories,
    parameters files, and several other things like that.
    """

    @property
    def protocol_basename(self):
        return os.path.basename(self.protocol_path)

    @property
    def protocol_path(self):
        raise NotImplementedError

    @property
    def final_protocol_path(self):
        return os.path.join(self.focus_dir, self.protocol_basename + '.final')

    @property
    def input_dir(self):
        return os.path.join(self.focus_dir, 'inputs')

    @property
    def input_paths(self):
        return glob.glob(os.path.join(self.input_dir, '*.pdb.gz'))

    def input_path(self, job_info):
        raise NotImplementedError

    def input_basename(self, job_info):
        return os.path.basename(self.input_path(job_info))

    @property
    def input_names(self):
        return [os.path.basename(x) for x in self.input_paths]

    @property
    def output_dir(self):
        return os.path.join(self.focus_dir, 'outputs')

    @property
    def output_subdirs(self):
        return [self.output_dir]

    @property
    def output_paths(self):
        return glob.glob(os.path.join(self.input_dir, '*.pdb.gz'))

    def output_path(self, job_info):
        prefix = self.output_prefix(job_info)
        basename = os.path.basename(self.input_path(job_info)[:-len('.pdb.gz')])
        suffix = self.output_suffix(job_info)
        return prefix + basename + suffix + '.pdb.gz'

    def output_basename(self, job_info):
        return os.path.basename(self.output_path(job_info))

    def output_prefix(self, job_info):
        return self.output_dir + '/'

    def output_suffix(self, job_info):
        return ''

    @property
    def io_dirs(self):
        return [self.input_dir] + self.output_subdirs

    @property
    def log_dir(self):
        return os.path.join(self.focus_dir, 'logs')

    @property
    def rsync_recursive_flag(self):
        return True

    @property
    def rsync_exclude_patterns(self):
        parent_patterns = super(BigJobWorkspace, self).rsync_exclude_patterns
        return parent_patterns + ['logs/', '*.sc']

    def job_info_path(self, job_id):
        return os.path.join(self.focus_dir, '{0}.json'.format(job_id))

    @property
    def all_job_info_paths(self):
        return glob.glob(os.path.join(self.focus_dir, '*.json'))

    @property
    def all_job_info(self):
        from . import big_jobs
        return [big_jobs.read_job_info(x) for x in self.all_job_info_paths]

    @property
    def unclaimed_inputs(self):
        inputs = set(self.input_names)
        for params in self.all_job_info:
            inputs -= set(params['inputs'])
        return sorted(inputs)

    def make_dirs(self):
        Workspace.make_dirs(self)
        scripting.mkdir(self.input_dir)
        scripting.mkdir(self.output_dir)
        scripting.mkdir(self.log_dir)

    def clear_inputs(self):
        scripting.clear_directory(self.input_dir)

    def clear_outputs(self):
        scripting.clear_directory(self.output_dir)
        scripting.clear_directory(self.log_dir)

        for path in self.all_job_info_paths:
            os.remove(path)


class WithFragmentLibs(object):
    """
    Provide paths needed to interact with fragment libraries.

    This is a mixin class that provides a handful of paths and features useful
    for working with fragment libraries.
    """

    @property
    def fasta_path(self):
        return os.path.join(self.fragments_dir, 'input.fasta')

    @property
    def fragments_dir(self):
        return os.path.join(self.focus_dir, 'fragments')

    def fragments_tag(self, input_path):
        return os.path.basename(input_path)[:4]

    def fragments_missing(self, input_path):
        tag = self.fragments_tag(input_path)
        frag_dir_glob = os.path.join(self.fragments_dir, tag+'?')
        frag_dirs = glob.glob(frag_dir_glob)

        # If there aren't any fragment directories, then there definitely 
        # aren't any fragments.
        if not frag_dirs:
            return True

        # If there are any fragment directories without fragment maps, then a 
        # job died and we're missing some fragments.
        for dir in frag_dirs:
            frag_map_path = os.path.join(dir, 'fragment_file_map.json')
            if not os.path.exists(frag_map_path):
                return True

        return False

    def fragments_info(self, input_path):
        # Typically, there is one output directory for each chain that
        # fragments are being generated for.

        tag = self.fragments_tag(input_path)
        frag_map_glob = os.path.join(self.fragments_dir, tag+'?', 'fragment_file_map.json')
        frag_map = {}

        for path in glob.glob(frag_map_glob):
            with open(path) as file:
                frag_map.update(json.load(file))

        # Sort the fragments first by decreasing size of the fragments (because
        # rosetta insists that the fragment arguments be in this order) and
        # second alphabetically (for aesthetics).

        frag_size = lambda x: frag_map[x]['frag_sizes']

        frag_paths = sorted(frag_map)
        frag_paths = sorted(frag_paths, key=frag_size, reverse=True)

        frag_sizes = [frag_size(x) for x in frag_paths]
        frag_paths = [os.path.join(self.fragments_dir, x) for x in frag_paths]

        # If no size-1 fragments were generated, but larger fragments were,
        # also add the 'none' pseudo-path.  This will cause rosetta to make
        # size-1 fragments from the next largest fragment set.

        if frag_sizes and frag_sizes[-1] > 1:
            frag_paths.append('none')
            frag_sizes.append(1)

        return frag_paths, frag_sizes

    def fragments_flags(self, input_path):
        flags = []
        paths, sizes = self.fragments_info(input_path)

        if paths and sizes:
            flags.append('-loops:frag_sizes')
            flags.extend(map(str, sizes))
            flags.append('-loops:frag_files')
            flags.extend(paths)

        return flags

    def clear_fragments(self):
        scripting.clear_directory(self.fragments_dir)


class RestrainedModels(BigJobWorkspace, WithFragmentLibs):

    def __init__(self, root):
        BigJobWorkspace.__init__(self, root)

    @staticmethod
    def from_directory(directory):
        return RestrainedModels(os.path.join(directory, '..'))

    @property
    def focus_name(self):
        return 'build_models'

    @property
    def focus_dir(self):
        return os.path.join(self.root_dir, '01_{0}'.format(self.focus_name))

    @property
    def protocol_path(self):
        return self.build_script_path

    @property
    def input_dir(self):
        return self.root_dir

    def input_path(self, parameters):
        return self.input_pdb_path

    @property
    def input_paths(self):
        return [self.input_pdb_path]

    def output_prefix(self, job_info):
        return os.path.join(
                self.output_dir,
                '{0}_{1:06d}_'.format(job_info['job_id'], job_info['task_id']),
        )


class FixbbDesigns(BigJobWorkspace):

    def __init__(self, root, round):
        BigJobWorkspace.__init__(self, root)
        self.round = int(round)

    @staticmethod
    def from_directory(directory):
        root = os.path.join(directory, '..')
        round = int(directory.split('_')[-1])
        return FixbbDesigns(root, round)

    @property
    def predecessor(self):
        if self.round == 1:
            return RestrainedModels(self.root_dir)
        else:
            return ValidatedDesigns(self.root_dir, self.round - 1)

    @property
    def focus_name(self):
        return 'design_models'

    @property
    def focus_dir(self):
        assert self.round > 0
        prefix = 2 * self.round
        subdir = '{0:02}_{1}_round_{2}'.format(prefix, self.focus_name, self.round)
        return os.path.join(self.root_dir, subdir)

    @property
    def protocol_path(self):
        return self.design_script_path
    def input_path(self, job_info):
        bb_models = job_info['inputs']
        bb_model = bb_models[job_info['task_id'] % len(bb_models)]
        return os.path.join(self.input_dir, bb_model)

    def output_suffix(self, job_info):
        design_id = job_info['task_id'] // len(job_info['inputs'])
        return '_{0:03}'.format(design_id)


class ValidatedDesigns(BigJobWorkspace, WithFragmentLibs):

    def __init__(self, root, round):
        BigJobWorkspace.__init__(self, root)
        self.round = int(round)

    @staticmethod
    def from_directory(directory):
        root = os.path.join(directory, '..')
        round = int(directory.strip('/').split('_')[-1])
        return ValidatedDesigns(root, round)

    @property
    def predecessor(self):
        return FixbbDesigns(self.root_dir, self.round)

    @property
    def focus_name(self):
        return 'validate_designs'

    @property
    def focus_dir(self):
        assert self.round > 0
        prefix = 2 * self.round + 1
        subdir = '{0:02}_{1}_round_{2}'.format(prefix, self.focus_name, self.round)
        return os.path.join(self.root_dir, subdir)

    @property
    def protocol_path(self):
        return self.validate_script_path

    def input_path(self, job_info):
        designs = job_info['inputs']
        design = designs[job_info['task_id'] % len(designs)]
        return os.path.join(self.input_dir, design)

    @property
    def output_subdirs(self):
        return sorted(glob.glob(os.path.join(self.output_dir, '*/')))

    def output_subdir(self, input_name):
        basename = os.path.basename(input_name[:-len('.pdb.gz')])
        return os.path.join(self.output_dir, basename)

    def output_prefix(self, job_info):
        input_model = self.input_basename(job_info)[:-len('.pdb.gz')]
        return os.path.join(self.output_dir, input_model) + '/'

    def output_suffix(self, job_info):
        return '_{0:03d}'.format(job_info['task_id'] / len(job_info['inputs']))


class AdditionalMetricWorkspace (Workspace):

    def __init__(self, directory):
        self.directory = os.path.abspath(directory)
        self._root_dir = os.path.join(root_from_dir(directory),'..')

    @property
    def focus_dir(self):
        return self.directory

    @property
    def focus_name(self):
        return self.focus_dir.split('/')[-1:][0]

    @property
    def input_dirs(self):
        input_dirs = []
        for path in self.input_names:
            input_dirs.append(os.path.dirname(path))
        return sorted(list(set(input_dirs)))

    @property
    def input_names(self):
        inputs = []
        for subdir, dirs, files in os.walk(self.root_directory):
            for file in files:
                if file.endswith('.pdb') or file.endswith('.pdb.gz'):
                    inputs.append(os.path.join(subdir, file))
        return inputs

    def input_path(self, job_info):
        return self.input_names[job_info['task_id']]

    @property
    def output_dirs(self):
        output_dirs = []
        for path in self.input_names:
            dirname = os.path.dirname(path)
            output_dirs.append(os.path.join(dirname, 'extra_metrics')) 
        return sorted(list(set(output_dirs)))

    def output_prefix(self, job_info):
        path = ''
        for item in \
        metric_workspace.input_path(job_info).split('/')[:-1]:
            path = os.path.join(path,item)
        return os.path.join(path, 'extra_metrics')

    @property
    def output_suffix(self, job_info):
        return '_extra_metric'

    def make_output_dirs(self):
        for output_dir in self.output_dirs:
            scripting.mkdir(output_dir)

    def set_metrics_script_path(self, path):
        self.metrics_script_path = path

    @property
    def final_protocol_path(self):
        return self.metrics_script_path

    @property
    def log_dir(self):
        return os.path.join(self.root_directory, 'logs')


def big_job_dir():
    return os.path.join(os.path.dirname(__file__), 'big_jobs')

def big_job_path(basename):
    return os.path.join(big_job_dir(), basename)

def workspace_from_dir(directory, recurse=True):
    """
    Construct a workspace object from a directory name.  If recurse=True, this
    function will search down the directory tree and return the first workspace
    it finds.  If recurse=False, an exception will be raised if the given
    directory is not a workspace.  Workspace identification requires a file
    called 'workspace.pkl' to be present in each workspace directory, which can
    unfortunately be a little fragile.
    """
    directory = os.path.abspath(directory)
    pickle_path = os.path.join(directory, 'workspace.pkl')

    # Make sure the given directory contains a 'workspace' file.  This file is
    # needed to instantiate the right kind of workspace.

    if not os.path.exists(pickle_path):
        if recurse:
            parent_dir = os.path.dirname(directory)

            # Keep looking for a workspace as long as we haven't hit the root
            # of the file system.  If an exception is raised, that means no
            # workspace was found.  Catch and re-raise the exception so that
            # the name of the directory reported in the exception is meaningful
            # to the user.

            try:
                return workspace_from_dir(parent_dir, parent_dir != '/')
            except WorkspaceNotFound:
                raise WorkspaceNotFound(directory)
        else:
            raise WorkspaceNotFound(directory)

    # Load the 'workspace' file and create a workspace.

    with open(pickle_path) as file:
        workspace_class = pickle.load(file)

    return workspace_class.from_directory(directory)

def root_from_dir(directory, recurse=True):
    """
    Similar to workspace_from_dir, but this returns the root directory
    of a workspace rather than a workspace object. 
    """

    directory = os.path.abspath(directory)
    pickle_path = os.path.join(directory, 'workspace.pkl')

    # Make sure the given directory contains a 'workspace' file.  This file is
    # needed to instantiate the right kind of workspace.

    if not os.path.exists(pickle_path):
        if recurse:
            parent_dir = os.path.dirname(directory)

            # Keep looking for a workspace as long as we haven't hit the root
            # of the file system.  If an exception is raised, that means no
            # workspace was found.  Catch and re-raise the exception so that
            # the name of the directory reported in the exception is meaningful
            # to the user.

            try:
                return root_from_dir(parent_dir, parent_dir != '/')
            except WorkspaceNotFound:
                raise WorkspaceNotFound(directory)
        else:
            raise WorkspaceNotFound(directory)

    # Return the directory in which the pkl file was found.

    return pickle_path[:-len('workspace.pkl')]

def load_loops(directory, loops_path=None):
    """
    Return a list of tuples indicating the start and end points of the loops
    that were sampled in the given directory.
    """

    if loops_path is None:
        workspace = workspace_from_dir(directory)
        loops_path = workspace.loops_path

    from klab.rosetta.input_files import LoopsFile
    loops_parser = LoopsFile.from_filepath(loops_path)

    # We have to account for some weird indexing behavior in the loops file
    # parser that I don't really understand.  It seems to shrink the loop by
    # one residue on each side.  At first I thought it might be trying to
    # convert the indices to python indexing, but on second thought I have no
    # idea what it's trying to do.

    return [(x-1, y+1) for x, y in loops_parser.get_distinct_segments()]

def load_resfile(directory, resfile_path=None):
    """
    Return a list of tuples indicating the start and end points of the loops
    that were sampled in the given directory.
    """

    if resfile_path is None:
        workspace = workspace_from_dir(directory)
        resfile_path = workspace.resfile_path

    from klab.rosetta.input_files import Resfile
    return Resfile(resfile_path)

def fetch_data(directory, remote_url=None, recursive=True, include_logs=False, dry_run=False):
    import os, subprocess

    workspace = workspace_from_dir(directory)

    # Try to figure out the remote URL from the given directory, if a
    # particular URL wasn't given.

    if remote_url is None:
        remote_url = workspace.rsync_url

    # Make sure the given directory is actually a directory.  (It's ok if it
    # doesn't exist; rsync will create it.)

    if os.path.exists(directory) and not os.path.isdir(directory):
        print "Skipping {}: not a directory.".format(directory)
        return

    # Compose an rsync command to copy the files in question.  Then either run
    # or print that command, depending on what the user asked for.

    rsync_command = [
            'rsync', '-av',
    ] +   (['--no-recursive'] if not recursive else []) + [
            '--exclude', 'rosetta',
            '--exclude', 'rsync_url',
            '--exclude', 'fragments',
            '--exclude', 'core.*',
            '--exclude', 'sequence_profile*',
    ]
    if not include_logs:
        rsync_command += [
                '--exclude', 'logs',
                '--exclude', '*.sc',
        ]

    # This code is trying to combine the remote URL with a directory path.
    # Originally I was just using os.path.join() to do this, but that caused a
    # bug when the URL was something like "chef:".  This is supposed to specify
    # a path relative to the user's home directory, but os.path.join() adds a
    # slash and turns the path into an absolute path.

    sep = '' if remote_url.endswith(':') else '/'
    remote_dir = os.path.normpath(
            remote_url + sep + os.path.relpath(directory, workspace.parent_dir))
    rsync_command += [
            remote_dir + '/',
            directory,
    ]

    if dry_run:
        print ' '.join(rsync_command)
    else:
        subprocess.call(rsync_command)

def fetch_and_cache_data(directory, remote_url=None, recursive=True, include_logs=False):
    from . import structures
    fetch_data(directory, remote_url, recursive, include_logs)

    # Don't try to cache anything if nothing has been downloaded yet.
    if glob.glob(os.path.join(directory, '*.pdb*')):
        structures.load(directory)

def push_data(directory, remote_url=None, recursive=True, dry_run=False):
    import os, subprocess

    workspace = workspace_from_dir(directory)

    if remote_url is None:
        remote_url = workspace.rsync_url

    remote_dir = os.path.normpath(os.path.join(
            remote_url, os.path.relpath(directory, workspace.parent_dir)))

    rsync_command = [
            'rsync', '-av',
    ] +   (['--no-recursive'] if not recursive else []) + [
            '--exclude', 'rosetta',
            '--exclude', 'rsync_url',
            '--exclude', 'logs',
            directory + '/', remote_dir,
    ]

    if dry_run:
        print ' '.join(rsync_command)
    else:
        subprocess.call(rsync_command)


class PipelineError (IOError):

    def __init__(self, message):
        super(PipelineError, self).__init__(message)
        self.no_stack_trace = True


class PathNotFound (PipelineError):

    def __init__(self, path, *directories):
        if len(directories) == 0:
            message = "'{0}' not found.".format(path)

        elif len(directories) == 1:
            path = os.path.join(directories[0], path)
            message = "'{0}' not found.".format(path)

        else:
            message = "'{0}' not found.  Looked in:".format(path)
            for directory in directories:
                message += "\n    " + directory

        PipelineError.__init__(self, message)


class RosettaNotFound (PipelineError):

    def __init__(self, workspace):
        PipelineError.__init__(self, """\
No rosetta checkout found in '{0.root_dir}'.
Use the following command to manually create a symlink to a rosetta checkout:

$ ln -s /path/to/rosetta/checkout {0.rosetta_dir}""")


class WorkspaceNotFound (PipelineError):

    def __init__(self, root):
        message = "'{0}' is not a workspace.".format(root)
        PipelineError.__init__(self, message)


class UnspecifiedRemoteHost (PipelineError):

    def __init__(self):
        PipelineError.__init__(self, "No remote host specified.")
