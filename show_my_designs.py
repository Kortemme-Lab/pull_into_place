#!/usr/bin/env python2
# encoding: utf-8

import os, glob, numpy as np
from libraries import pipeline, structures, show_my_designs as smd

class PipDesign (smd.Design):

    def _load_models(self, use_cache):
        if not os.path.exists(self.directory):
            raise IOError("'{}' does not exist".format(self.directory))
        if not os.path.isdir(self.directory):
            raise IOError("'{}' is not a directory".format(self.directory))
        if not os.listdir(self.directory):
            raise IOError("'{}' is empty".format(self.directory))
        if not glob.glob(os.path.join(self.directory, '*.pdb*')):
            raise IOError("'{}' doesn't contain any PDB files".format(self.directory))

        try:
            self.workspace = pipeline.workspace_from_dir(self.directory)
        except pipeline.WorkspaceNotFound:
            raise IOError("'{}' is not a workspace".format(self.directory))
        if not any(os.path.samefile(self.directory, x) for x in self.workspace.pdb_dirs):
            raise IOError("'{}' is not meant to be visualized".format(self.directory))

        self._models = structures.load(
                self.directory,
                restraints_path=self.workspace.restraints_path,
                use_cache=use_cache)

        if len(self.defined_metrics) == 0:
            raise IOError("no metrics defined for the models in '{}'".format(self.directory))
        if len(self.defined_metrics) == 1:
            defined_metric = self.defined_metrics.pop()
            raise IOError("only found one metric '{}' for the models in '{}', need at least two".format(defined_metric, self.directory))



smd.Design = PipDesign

smd.default_x_metric = 'restraint_dist'
smd.default_y_metric = 'total_score'

smd.metric_titles['total_score'] = u"Total Score (REU)"
smd.metric_titles['restraint_dist'] = u"Restraint Satisfaction (Å)"
smd.metric_titles['loop_dist'] = u"Loop RMSD (Å)"
smd.metric_titles['buried_unsat_score'] = u"Δ Buried Unsats"
smd.metric_titles['dunbrack_score'] = u"Dunbrack Score (REU)"

smd.metric_limits['total_score'] = lambda x: (min(x), np.percentile(x, 85))
smd.metric_limits['restraint_dist'] = lambda x: (min(x), np.percentile(x, 95))
smd.metric_limits['loop_dist'] = lambda x: (min(x), np.percentile(x, 95))

smd.metric_guides['restraint_dist'] = 1.0
smd.metric_guides['loop_dist'] = 1.0

smd.main()
