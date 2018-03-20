#!/usr/bin/env python3

from pull_into_place import RestrainedModels, big_jobs

def test_finalize_protocol():
    workspace = RestrainedModels('workspaces/test_finalize_protocol')
    params = dict(test_param='Hello world!')

    big_jobs.finalize_protocol(workspace, params)
    
    with open(workspace.final_protocol_path) as file:
        actual_output = file.read()

    assert actual_output == """\
<!-- A: build_models/a.xml -->
<!-- B: project_params/build_models/b.xml -->
<!-- C: c.xml -->
<!-- D: project_params/d.xml -->
<!-- E: standard_params/build_models/e.xml -->
<!-- F: standard_params/f.xml -->
<!-- project_params/build_models.xml -->

<!-- Focus name: build_models -->
<!-- Parameter: Hello world! -->"""






