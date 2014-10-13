#!/usr/bin/env python2

import os, glob
from tools import scripting

class Workspace:

    def __init__(self, name):
        self.name = name
        self._relative_path = '.'

    @property
    def root_path(self):
        return os.path.join(self._relative_path, self.name)

    @property
    def rosetta_path(self):
        return self.rosetta_subpath()

    def rosetta_subpath(self, *subpaths):
        return os.path.join(self.root_path, 'rosetta', *subpaths)

    @property
    def rosetta_scripts_path(self):
        return self.rosetta_subpath('source', 'bin', 'rosetta_scripts')

    @property
    def rosetta_database_path(self):
        return self.rosetta_subpath('database')

    @property
    def input_pdb_path(self):
        return os.path.join(self.root_path, 'input.pdb.gz')

    @property
    def loops_path(self):
        return os.path.join(self.root_path, 'loops')

    @property
    def resfile_path(self):
        return os.path.join(self.root_path, 'resfile')

    @property
    def restraints_path(self):
        return os.path.join(self.root_path, 'restraints')

    @property
    def flags_path(self):
        return os.path.join(self.root_path, 'flags')

    def required_paths(self):
        return [
                self.input_pdb_path,
                self.loops_path,
                self.resfile_path,
                self.flags_path,
                self.restraints_path,
                self.rosetta_path,
        ]

    def required_paths_exist(self):
        for path in self.required_paths():
            if not os.path.exists(path):
                return False
        return True

    def check_paths(self):
        for path in self.required_paths():
            if not os.path.exists(path):
                scripting.print_error_and_die("Missing '{0}'.", path)

    def cd(self, *subpaths):
        source = os.path.abspath(self._relative_path)
        target = os.path.abspath(os.path.join(*subpaths))
        self._relative_path = os.path.relpath(source, target)
        os.chdir(target)

    def exists(self):
        return os.path.exists(self.root_path)


class ForCluster:

    def job_params_path(self, job_id):
        return os.path.join(self.subdir_path, '{0}.json'.format(job_id))

    @property
    def all_job_params_paths(self):
        return glob.glob(os.path.join(self.subdir_path, '*.json'))

    @property
    def all_job_params(self):
        from libraries import big_job
        return [big_job.read_params(x) for x in self.all_job_params_paths]

    @property
    def stdout_dir(self):
        return os.path.join(self.subdir_path, 'stdout')

    @property
    def stderr_dir(self):
        return os.path.join(self.subdir_path, 'stderr')


class WithFragments:

    @property
    def fasta_path(self):
        return os.path.join(self.fragments_dir, 'input.fasta')

    @property
    def fragments_dir(self):
        return os.path.join(self.subdir_path, 'fragments')

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



class AllRestrainedModels (Workspace, ForCluster, WithFragments):

    def __init__(self, name):
        Workspace.__init__(self, name) 

    @property
    def subdir_path(self):
        return os.path.join(self.root_path, '01_all_restrained_models')

    @property
    def output_dir(self):
        return os.path.join(self.subdir_path, 'outputs')

    def make_dirs(self):
        scripting.mkdir(self.subdir_path)
        scripting.mkdir(self.output_dir)
        scripting.mkdir(self.fragments_dir)

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
    def subdir_path(self):
        return os.path.join(self.root_path, '02_best_restrained_models')

    @property
    def input_dir(self):
        return os.path.join(self.subdir_path, 'inputs')

    @property
    def output_dir(self):
        return os.path.join(self.subdir_path, 'outputs')

    @property
    def predecessor(self):
        return AllRestrainedModels(self.name)


class AllFixbbWorkspaces (Workspace, ForCluster):

    def __init__(self, name, round):
        Workspace.__init__(self, name)
        self.round = round

    @property
    def subdir_path(self):
        assert self.round > 0
        prefix = 3 + 4 * (self.round - 1)
        subdir = '{0}_all_fixbb_designs_round_{1}'.format(prefix, self.round)
        return os.path.join(self.root_path, subdir)

    @property
    def input_dir(self):
        return os.path.join(self.subdir_path, 'inputs')

    @property
    def output_dir(self):
        return os.path.join(self.subdir_path, 'outputs')

    @property
    def predecessor(self):
        if self.round == 1:
            return BestRestrainedModels(self.name)
        else:
            return BestValidatedWorkspaces(self.name, self.round - 1)



def from_directory(directory):
    directory = os.path.abspath(directory)
    if directory == '/':
        scripting.print_error_and_die("No designs found in any subdirectories of specified path.")

    workspace = Workspace(directory)
    if not workspace.required_paths_exist():
        parent_dir = os.path.join(directory, '..')
        workspace = Workspace.from_subdir(parent_dir)

    return workspace
    
