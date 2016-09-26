***************
Pull Into Place
***************
Pull Into Place (PIP) is a protocol to design protein functional groups with 
sub-angstrom accuracy.  The protocol is based on two ideas: 1) using restraints 
to define the geometry you're trying to design and 2) using an unrestrained 
simulations to test designs.

.. image:: https://img.shields.io/pypi/v/pull_into_place.svg
   :target: https://pypi.python.org/pypi/pull_into_place

.. image:: https://img.shields.io/pypi/pyversions/pull_into_place.svg
   :target: https://pypi.python.org/pypi/pull_into_place

.. image:: https://readthedocs.org/projects/pull_into_place/badge/?version=latest
   :target: http://pull_into_place.readthedocs.io/en/latest/?badge=latest

The design pipeline orchestrated by PIP has the following steps:

1. Define your project.  This entails creating an input PDB file and preparing 
   it for use with rosetta, creating a restraints file that specifies your 
   desired geometry, creating a resfile that specifies which residues are 
   allowed to design, and creating a loop file that specifies where backbone 
   flexibility will be considered::

   $ pull_into_place 01_setup_workspace ...
   $ pull_into_place 02_setup_model_fragments ...

2. Build a large number of models that plausibly support your desired geometry 
   by running flexible backbone Monte Carlo simulations restrained to stay near 
   said geometry.  The goal is to strike a balance between finding models that 
   are realistic and finding models that satisfy your restraints::

   $ pull_into_place 03_build_models ...

3. Filter out models that don't meet your quality criteria::

   $ pull_into_place 04_pick_models_to_design ...

4. Generate a number of designs for each model remaining::

   $ pull_into_place 05_design_models ...

5. Pick a small number of designs to validate.  Typically I generate 100,000 
   designs and can only validate 50-100.  I've found that randomly picking 
   designs according to the Boltzmann weight of their rosetta score gives a 
   nice mix of designs that are good but not too homogeneous::

   $ pull_into_place 06_pick_designs_to_validate ...

6. Validate the designs using unrestrained Monte Carlo simulations.  Designs 
   that are "successful" will have a funnel on the left side of their score vs 
   rmsd plots::

   $ pull_into_place 07_setup_design_fragments ...
   $ pull_into_place 08_validate_designs ...

7. Optionally take the decoys with the best geometry from the validation run 
   (even if they didn't score well) and feed them back into step 4.  Second and 
   third rounds of simulation usually produce much better results than the 
   first, because the models being designed are more realistic.  Additional 
   rounds of simulation give diminishing returns, and may be more effected by 
   some of rosetta's pathologies (i.e. it's preference for aromatic residues)::

   $ pull_into_place 04_pick_models_to_design ...
   $ pull_into_place 05_design_models ...
   $ pull_into_place 06_pick_designs_to_validate ...
   $ pull_into_place 07_setup_design_fragments ...
   $ pull_into_place 08_validate_designs ...

8. Generate a report summarizing a variety of quality metrics for each design.  
   This report is meant to help you pick designs to test experimentally::

   $ pull_into_place 09_compare_best_designs ...

