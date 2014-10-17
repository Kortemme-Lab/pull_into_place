#!/usr/bin/env python2

import os, glob
from tools import scripting

class Workspace:

    def __init__(self, name):
        self.name = name
        self._relative_path = ''

    @property
    def root_dir(self):
        return os.path.join(self._relative_path, self.name)

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
    def flags_path(self):
        return self.find_path('flags')

    @property
    def rsync_url_path(self):
        return self.find_path('rsync_url')

    @property
    def rsync_url(self):
        with open(self.rsync_url_path) as file:
            return file.read().strip()

    @rsync_url.setter
    def set_rsync_url(self, url):
        with open(self.rsync_url_path, 'w') as file:
            return file.write(url.strip() + '\n')

    def find_path(self, basename, *directories):
        if not directories:
            directories = self.focus_dir, self.root_dir

        default_path = None

        for directory in directories:
            path = os.path.join(directory, basename)
            if default_path is None:
                default_path = path
            if os.path.exists(path):
                return path

        return default_path

    def required_paths(self):
        return [
                self.rosetta_dir,
                self.input_pdb_path,
                self.loops_path,
                self.resfile_path,
                self.flags_path,
                self.restraints_path,
        ]

    def check_paths(self):
        for path in self.required_paths():
            if not os.path.exists(path):
                raise PathNotFound(path)

    def make_dirs(self):
        scripting.mkdir(self.focus_dir)

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

    def __init__(self, name):
        Workspace.__init__(self, name) 

    @property
    def focus_dir(self):
        return os.path.join(self.root_dir, '01_all_restrained_models')

    @property
    def output_dir(self):
        return os.path.join(self.focus_dir, 'outputs')

    def make_dirs(self):
        Workspace.make_dirs()
        scripting.mkdir(self.fragments_dir)
        scripting.mkdir(self.output_dir)
        scripting.mkdir(self.stdout_dir)
        scripting.mkdir(self.stderr)

    def clear_models(self):
        scripting.clear_directory(self.output_dir)
        scripting.clear_directory(self.stdout_dir)
        scripting.clear_directory(self.stderr_dir)
    
        for path in self.all_job_params_paths:
            os.remove(path)


class BestRestrainedModels (Workspace):

    def __init__(self, name):
        Workspace.__init__(self, name)

    @property
    def focus_dir(self):
        return os.path.join(self.root_dir, '02_best_restrained_models')

    @property
    def input_dir(self):
        return os.path.join(self.focus_dir, 'inputs')

    @property
    def output_dir(self):
        return os.path.join(self.focus_dir, 'outputs')

    @property
    def predecessor(self):
        return AllRestrainedModels(self.name)


class AllFixbbWorkspaces (Workspace, WithCluster):

    def __init__(self, name, round):
        Workspace.__init__(self, name)
        self.round = round

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
    def output_dir(self):
        return os.path.join(self.focus_dir, 'outputs')

    @property
    def predecessor(self):
        if self.round == 1:
            return BestRestrainedModels(self.name)
        else:
            return BestValidatedWorkspaces(self.name, self.round - 1)



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



def pipeline_dir():
    dir = os.path.join(os.path.dirname(__file__), '..')
    return os.path.realpath(dir)

def big_job_dir():
    return os.path.join(pipeline_dir(), 'big_jobs')

def big_job_path(basename):
    return os.path.join(template_dir(), basename)

def from_directory(directory):
    directory = os.path.abspath(directory)

    if directory == '/':
        scripting.print_error_and_die("No designs found in any subdirectories of given path.")

    try:
        workspace = Workspace(directory)
        workspace.check_paths()
        return workspace

    except PathNotFound:
        parent_dir = os.path.join(directory, '..')
        return from_directory(parent_dir)

