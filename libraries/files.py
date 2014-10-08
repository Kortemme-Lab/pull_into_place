#!/usr/bin/env python

import os

class Design:

    def __init__(self, name):
        self.name = name

    @property
    def root_path(self):
        return os.path.join('designs', self.name)

    @property
    def inverse_path(self):
        dots = ['..' for i in range(1 + self.root_path.count('/'))]
        return os.path.join(*dots)

    @property
    def rosetta_path(self):
        return os.path.join(self.root_path, 'rosetta')

    @property
    def input_pdb_path(self):
        return os.path.join(self.root_path, 'input.pdb')

    @property
    def loops_path(self):
        return os.path.join(self.root_path, 'loops')

    @property
    def resfile_path(self):
        return os.path.join(self.root_path, 'resfile')

    @property
    def flags_path(self):
        return os.path.join(self.root_path, 'flags')

    @property
    def restraints_path(self):
        return os.path.join(self.root_path, 'restraints')

    def exists(self):
        return os.path.exists(self.root_path)

    def check_rosetta_path(self):
        if not os.path.exists(self.rosetta_path):
            raise RosettaNotFound(self.rosetta_path)


class AllRestrainedModels (Design):

    def __init__(self, name):
        Design.__init__(self, name) 

    @property
    def subdir_path(self):
        return os.path.join(self.root_path, '01_all_restrained_models')

    @property
    def input_path(self):
        return os.path.join(self.subdir_path, 'input.pdb')

    @property
    def output_dir(self):
        return os.path.join(self.subdir_path, 'outputs')


class BestRestrainedModels (Design):

    def __init__(self, name):
        Design.__init__(self, name)

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


class AllFixbbDesigns (Design):

    def __init__(self, name, round):
        Design.__init__(self, name)
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
            return BestValidatedDesigns(self.name, self.round - 1)



class RosettaNotFound (RuntimeError):

    def __init__(self, expected_path):
        message = "Expected location: {0}".format(expected_path)
        super(RosettaNotFound, self).__init__(message)
                
