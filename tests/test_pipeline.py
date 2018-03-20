#!/usr/bin/env python3

import os.path
from pull_into_place import Workspace, RestrainedModels

def test_standard_params():
    w = RestrainedModels('workspaces/test_standard_params')

    assert os.path.samefile(
            w.loops_path,
            'workspaces/test_standard_params/standard_params/build_models/loops')

    assert os.path.samefile(
            w.build_script_path,
            'workspaces/test_standard_params/standard_params/build_models.xml')

    assert os.path.samefile(
            w.shared_defs_path,
            'workspaces/test_standard_params/standard_params/shared_defs.xml')

def test_project_params():
    w = RestrainedModels('workspaces/test_project_params')

    assert os.path.samefile(
            w.loops_path,
            'workspaces/test_project_params/project_params/build_models/loops')

    assert os.path.samefile(
            w.build_script_path,
            'workspaces/test_project_params/project_params/build_models.xml')

    assert os.path.samefile(
            w.shared_defs_path,
            'workspaces/test_project_params/standard_params/shared_defs.xml')

def test_root_params():
    w = RestrainedModels('workspaces/test_root_params')

    assert os.path.samefile(
            w.loops_path,
            'workspaces/test_root_params/build_models/loops')

    assert os.path.samefile(
            w.build_script_path,
            'workspaces/test_root_params/build_models.xml')

    assert os.path.samefile(
            w.shared_defs_path,
            'workspaces/test_root_params/standard_params/shared_defs.xml')

def test_two_loops():
    w = Workspace('workspaces/test_two_loops')

    assert w.loop_segments == [(26, 51), (198, 203)]
    assert w.largest_loop.start == 26
    assert w.largest_loop.end == 51

