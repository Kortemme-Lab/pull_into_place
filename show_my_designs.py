#!/usr/bin/env python2
# encoding: utf-8

import os, glob, numpy as np
from libraries import pipeline, structures, show_my_designs as smd

class PipDesign (smd.Design):

    def _load_models(self, use_cache):
        self._models = structures.load(
                self.directory,
                use_cache=use_cache,
        )



smd.Design = PipDesign

smd.default_x_metric = 'restraint_dist'
smd.default_y_metric = 'total_score'

smd.metric_titles['total_score'] = u"Total Score (REU)"
smd.metric_titles['dunbrack_score'] = u"Dunbrack Score (REU)"
smd.metric_titles['buried_unsat_score'] = u"Δ Buried Unsats"
smd.metric_titles['restraint_dist'] = u"Restraint Satisfaction (Å)"
smd.metric_titles['loop_dist'] = u"Loop RMSD (Å)"

smd.metric_limits['total_score'] = lambda x: (min(x), np.percentile(x, 85))
smd.metric_limits['restraint_dist'] = lambda x: (0, np.percentile(x, 95))
smd.metric_limits['loop_dist'] = lambda x: (0, np.percentile(x, 95))

smd.metric_guides['restraint_dist'] = 1.0
smd.metric_guides['loop_dist'] = 1.0

smd.main()
