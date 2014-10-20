#!/usr/bin/env python2

import os, glob, pickle
from tools import scripting

class Workspace (object):

    def __init__(self, root):
        root = os.path.normpath(root)
        self._root_basename = os.path.basename(root)
        self._root_dirname = os.path.dirname(root)

    @classmethod
    def from_directory(cls, directory):
        # Force subclasses to reimplement this method
        if cls != Workspace:
            raise NotImplementedError

        return Workspace(directory)

    @property
    def root_dir(self):
        return os.path.join(self._root_dirname, self._root_basename)

    @property
    def focus_dir(self):
        return self.root_dir

    @property
    def rosetta_dir(self):
        return self.find_path('rosetta')

    @property
    def rosetta_scripts_path(self):
        return self.rosetta_subpath('source', 'bin', 'rosetta_scripts')

    @property
    def rosetta_database_path(self):
        return self.rosetta_subpath('database')

    def rosetta_subpath(self, *subpaths):
        return os.path.join(self.rosetta_dir, *subpaths)

    @property
    def input_pdb_path(self):
        return self.find_path('input.pdb.gz')

    @property
    def loops_path(self):
        return self.find_path('loops')

    @property
    def resfile_path(self):
        return self.find_path('resfile')

    @property
    def restraints_path(self):
        return self.find_path('restraints')

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
    def flags_path(self):
        return self.find_path('flags')

    @property
    def rsync_url_path(self):
        return self.find_path('rsync_url')

    @property
    def rsync_url(self):
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

    def find_path(self, basename):
        custom_path = os.path.join(self.focus_dir, basename)
        default_path = os.path.join(self.root_dir, basename)
        return custom_path if os.path.exists(custom_path) else default_path

    def required_paths(self):
        return [
                self.rosetta_dir,
                self.input_pdb_path,
                self.loops_path,
                self.resfile_path,
                self.restraints_path,
                self.flags_path,
        ]

    def check_paths(self):
        for path in self.required_paths():
            if not os.path.exists(path):
                raise PathNotFound(path)

    def make_dirs(self):
        scripting.mkdir(self.focus_dir)

        pickle_path = os.path.join(self.focus_dir, 'workspace.pkl')
        with open(pickle_path, 'w') as file:
            pickle.dump(self.__class__, file)

    def cd(self, *subpaths):
        source = os.path.abspath(self._relative_path)
        target = os.path.abspath(os.path.join(*subpaths))
        self._relative_path = os.path.relpath(source, target)
        os.chdir(target)

    def exists(self):
        return os.path.exists(self.focus_dir)


class BigJobWorkspace (Workspace):

    @property
    def input_dir(self):
        return os.path.join(self.focus_dir, 'inputs')

    @property
    def input_paths(self):
        return glob.glob(os.path.join(self.input_dir, '*.pdb.gz'))

    @property
    def output_dir(self):
        return os.path.join(self.focus_dir, 'outputs')

    @property
    def output_paths(self):
        return glob.glob(os.path.join(self.input_dir, '*.pdb.gz'))

    @property
    def stdout_dir(self):
        return os.path.join(self.focus_dir, 'stdout')

    @property
    def stderr_dir(self):
        return os.path.join(self.focus_dir, 'stderr')

    @property
    def rsync_recursive_flag(self):
        return True

    @property
    def rsync_exclude_patterns(self):
        parent_patterns = super(BigJobWorkspace, self).rsync_exclude_patterns
        return parent_patterns + ['stderr/', 'stdout/', '*.sc']

    def job_params_path(self, job_id):
        return os.path.join(self.focus_dir, '{0}.json'.format(job_id))

    @property
    def all_job_params_paths(self):
        return glob.glob(os.path.join(self.focus_dir, '*.json'))

    @property
    def all_job_params(self):
        from libraries import big_job
        return [big_job.read_params(x) for x in self.all_job_params_paths]

    @property
    def unclaimed_inputs(self):
        inputs = set(self.input_paths)
        for params in self.all_job_params:
            inputs -= set(params['inputs'])
        return sorted(inputs)

    def make_dirs(self):
        Workspace.make_dirs(self)
        scripting.mkdir(self.input_dir)
        scripting.mkdir(self.output_dir)
        scripting.mkdir(self.stdout_dir)
        scripting.mkdir(self.stderr_dir)

    def clear_inputs(self):
        scripting.clear_directory(self.input_dir)

    def clear_outputs(self):
        scripting.clear_directory(self.output_dir)
        scripting.clear_directory(self.stdout_dir)
        scripting.clear_directory(self.stderr_dir)

        for path in self.all_job_params_paths:
            os.remove(path)


class WithFragmentLibs (object):

    @property
    def fasta_path(self):
        return os.path.join(self.fragments_dir, 'input.fasta')

    @property
    def fragments_dir(self):
        return os.path.join(self.focus_dir, 'fragments')

    @property
    def fragments_sizes(self):
        import re

        sizes = []
        pattern = re.compile(r'(\d+)mers\.gz')

        for path in self.fragments_paths:
            match = pattern.search(path)
            if match: sizes.append(match.group(1))
            elif path == 'none': sizes.append('1')

        return sizes

    @property
    def fragments_paths(self):
        pattern = os.path.join(self.fragments_dir, '*', '*mers.gz')
        paths = [x for x in glob.glob(pattern) if 'score' not in x]
        return sorted(paths, reverse=True) + ['none']

    def make_dirs(self):
        scripting.mkdir(self.fragments_dir)

    def clear_fragments(self):
        scripting.clear_directory(self.fragments_dir)


class RestrainedModels (BigJobWorkspace, WithFragmentLibs):

    def __init__(self, root):
        BigJobWorkspace.__init__(self, root) 

    @staticmethod
    def from_directory(directory):
        return RestrainedModels(os.path.join(directory, '..'))

    @property
    def focus_dir(self):
        return os.path.join(self.root_dir, '01_restrained_models')

    @property
    def input_dir(self):
        return self.root_dir

    @property
    def input_paths(self):
        return [self.input_pdb_path]

    def make_dirs(self):
        BigJobWorkspace.make_dirs(self)
        WithFragmentLibs.make_dirs(self)


class FixbbDesigns (BigJobWorkspace):

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
    def focus_dir(self):
        assert self.round > 0
        prefix = 2 * self.round
        subdir = '{0:02}_fixbb_designs_round_{1}'.format(prefix, self.round)
        return os.path.join(self.root_dir, subdir)


class ValidatedDesigns (BigJobWorkspace, WithFragmentLibs):

    def __init__(self, root, round):
        BigJobWorkspace.__init__(self, root)
        self.round = int(round)

    @staticmethod
    def from_directory(directory):
        root = os.path.join(directory, '..')
        round = int(directory.split('_')[-1])
        return ValidatedDesigns(root, round)

    @property
    def predecessor(self):
        return FixbbDesigns(self.root_dir, self.round)

    @property
    def focus_dir(self):
        assert self.round > 0
        prefix = 2 * self.round + 1
        subdir = '{0:02}_validated_designs_round_{1}'.format(prefix, self.round)
        return os.path.join(self.root_dir, subdir)

    def output_subdir(self, input):
        basename = os.path.basename(input[:-len('.pdb.gz')])
        return os.path.join(self.output_dir, basename)

    def make_dirs(self):
        BigJobWorkspace.make_dirs(self)
        WithFragmentLibs.make_dirs(self)



def pipeline_dir():
    dir = os.path.join(os.path.dirname(__file__), '..')
    return os.path.realpath(dir)

def big_job_dir():
    return os.path.join(pipeline_dir(), 'big_jobs')

def big_job_path(basename):
    return os.path.join(big_job_dir(), basename)

def workspace_from_dir(directory, recurse=True):
    pickle_path = os.path.join(directory, 'workspace.pkl')

    # Make sure the given directory contains a 'workspace' file.  This file is 
    # needed to instantiate the right kind of workspace.
    
    if not os.path.exists(pickle_path):
        if recurse:
            parent_dir = os.path.dirname(directory)
            return workspace_from_dir(parent_dir, parent_dir == '/')
        else:
            raise WorkspaceNotFound(directory)

    # Load the 'workspace' file and create a workspace.

    with open(pickle_path) as file:
        workspace_class = pickle.load(file)

    return workspace_class.from_directory(directory)


class PathNotFound (IOError):

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

        super(PathNotFound, self).__init__(message)
        self.no_stack_trace = True


class WorkspaceNotFound (IOError):

    def __init__(self, root):
        message = "'{0}' is not a workspace.".format(root)
        super(WorkspaceNotFound, self).__init__(message)


