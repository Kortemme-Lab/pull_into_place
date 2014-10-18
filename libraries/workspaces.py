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
    def loopmodel_path(self):
        return self.find_path('loopmodel.xml')

    @property
    def fixbb_path(self):
        return self.find_path('fixbb.xml')

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


class WithCluster:

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
    def stdout_dir(self):
        return os.path.join(self.focus_dir, 'stdout')

    @property
    def stderr_dir(self):
        return os.path.join(self.focus_dir, 'stderr')


class WithFragments:

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

    def clear_fragments(self):
        scripting.clear_directory(self.fragments_dir)



class AllRestrainedModels (Workspace, WithCluster, WithFragments):

    def __init__(self, root):
        Workspace.__init__(self, root) 

    @staticmethod
    def from_directory(directory):
        return AllRestrainedModels(os.path.join(directory, '..'))

    @property
    def focus_dir(self):
        return os.path.join(self.root_dir, '01_all_restrained_models')

    @property
    def output_dir(self):
        return os.path.join(self.focus_dir, 'outputs')

    def make_dirs(self):
        Workspace.make_dirs(self)
        scripting.mkdir(self.fragments_dir)
        scripting.mkdir(self.output_dir)
        scripting.mkdir(self.stdout_dir)
        scripting.mkdir(self.stderr_dir)

    def clear_models(self):
        scripting.clear_directory(self.output_dir)
        scripting.clear_directory(self.stdout_dir)
        scripting.clear_directory(self.stderr_dir)
    
        for path in self.all_job_params_paths:
            os.remove(path)


class BestRestrainedModels (Workspace):

    def __init__(self, root):
        Workspace.__init__(self, root)

    @staticmethod
    def from_directory(directory):
        return BestRestrainedModels(os.path.join(directory, '..'))

    @property
    def predecessor(self):
        return AllRestrainedModels(self.root_path)

    @property
    def focus_dir(self):
        return os.path.join(self.root_dir, '02_best_restrained_models')

    @property
    def input_dir(self):
        return self.predecessor.output_dir

    @property
    def output_dir(self):
        return os.path.join(self.focus_dir, 'outputs')

    @property
    def output_paths(self):
        return glob.glob(os.path.join(self.output_dir, '*.pdb.gz'))

    @property
    def symlink_prefix(self):
        return os.path.relpath(self.input_dir, self.output_dir)

    def make_dirs(self):
        Workspace.make_dirs(self)
        scripting.mkdir(self.output_dir)

    def clear_outputs(self):
        scripting.clear_directory(self.output_dir)


class AllFixbbDesigns (Workspace, WithCluster):

    def __init__(self, root, round):
        Workspace.__init__(self, root)
        self.round = round

    @staticmethod
    def from_directory(directory):
        root = os.path.join(directory, '..')
        round = int(directory.split('_')[-1])
        return AllFixbbDesigns(root, round)

    @property
    def predecessor(self):
        if self.round == 1:
            return BestRestrainedModels(self.root_path)
        else:
            return BestValidatedWorkspaces(self.root_path, self.round - 1)

    @property
    def focus_dir(self):
        assert self.round > 0
        prefix = 3 + 4 * (self.round - 1)
        subdir = '{0}_all_fixbb_designs_round_{1}'.format(prefix, self.round)
        return os.path.join(self.root_dir, subdir)

    @property
    def input_dir(self):
        return os.path.join(self.focus_dir, 'inputs')

    @property
    def input_paths(self):
        return glob.glob(os.path.join(self.input_dir, '*.pdb.gz'))

    @property
    def output_dir(self):
        return os.path.join(self.focus_dir, 'outputs')

    def make_dirs(self):
        Workspace.make_dirs(self)
        os.symlink('inputs', predecessor.output_dir)



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
        message = "'{}' is not a workspace.".format(root)
        super(WorkspaceNotFound, self).__init__(message)



def pipeline_dir():
    dir = os.path.join(os.path.dirname(__file__), '..')
    return os.path.realpath(dir)

def big_job_dir():
    return os.path.join(pipeline_dir(), 'big_jobs')

def big_job_path(basename):
    return os.path.join(big_job_dir(), basename)

def from_directory(directory):
    pickle_path = os.path.join(directory, 'workspace.pkl')

    # Make sure the given directory contains a 'workspace' file.  This file is 
    # needed to instantiate the right kind of workspace.

    if not os.path.exists(pickle_path):
        raise WorkspaceNotFound(directory)

    # Load the 'workspace' file and create a workspace.

    with open(pickle_path) as file:
        workspace_class = pickle.load(file)

    return workspace_class.from_directory(directory)

