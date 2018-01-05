#!/usr/bin/env sh

# Assume rosetta is installed in a directory called `rosetta` in this 
# directory.  You can change this if Rosetta is installed elsewhere.
ROSETTA=rosetta

# Assume all of the input files related to KSI are in a directory called 
# `inputs` in this directory.  You can change this if you downloaded them 
# somewhere else.
KSI_INPUTS=inputs

# Name all the output files (a PDB and a log) with a consistent prefix.
OUTPUT_PREFIX=design_models

# Run rosetta with a reduced number of iterations.  This should finish in 30 
# minutes, but the results will not be meaningful.
stdbuf -oL $ROSETTA/source/bin/rosetta_scripts                              \
    -database $ROSETTA/database                                             \
    -in:file:s build_models_KSI_D38E_0001.pdb                               \
    -in:file:native $KSI_INPUTS/KSI_WT.pdb                                  \
    -out:prefix ${OUTPUT_PREFIX}_                                           \
    -out:overwrite                                                          \
    -parser:protocol $KSI_INPUTS/design_models.xml                          \
    -parser:script_vars                                                     \
        wts_file=$ROSETTA/database/scoring/weights/ref2015.wts              \
        cst_file=$KSI_INPUTS/restraints                                     \
        relax_cycles=2                                                      \
    -packing:resfile $KSI_INPUTS/resfile                                    \
    -relax:constrain_relax_to_start_coords yes                              \
    -extra_res_fa $KSI_INPUTS/EQU.fa.params                                 \
    -extra_res_cen $KSI_INPUTS/EQU.cen.params                               |
    tee $OUTPUT_PREFIX.log

mv design_models_build_models_KSI_D38E_0001_0001.pdb \
   design_models_KSI_D38E_0001.pdb \



