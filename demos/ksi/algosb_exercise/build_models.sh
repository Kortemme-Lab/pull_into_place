#!/usr/bin/env sh

# Assume rosetta is installed in a directory called `rosetta` in this 
# directory.  You can change this if Rosetta is installed elsewhere.
ROSETTA=rosetta

# Assume all of the input files related to KSI are in a directory called 
# `inputs` in this directory.  You can change this if you downloaded them 
# somewhere else.
KSI_INPUTS=inputs

# Name all the output files (a PDB and a log) with a consistent prefix.
OUTPUT_PREFIX=build_models

# Run rosetta with a very small number of iterations and rotamers.  This should 
# finish in 20 minutes, but the results will not be meaningful.
stdbuf -oL $ROSETTA/source/bin/rosetta_scripts                                         \
    -database $ROSETTA/database                                             \
    -in:file:s $KSI_INPUTS/KSI_D38E.pdb                                     \
    -in:file:native $KSI_INPUTS/KSI_WT.pdb                                  \
    -out:prefix ${OUTPUT_PREFIX}_                                           \
    -out:overwrite                                                          \
    -parser:protocol $KSI_INPUTS/build_models.xml                           \
    -parser:script_vars                                                     \
        wts_file=$ROSETTA/database/scoring/weights/ref2015.wts              \
        loop_file=$KSI_INPUTS/loops                                         \
        dont_mutate="26-35,37,38,46-51"                                     \
        fast="yes"                                                          \
    -lh:db_path $KSI_INPUTS/loophash_db                                     \
    -lh:loopsizes 6 7 8 9 10 11 12 13 14                                    \
    -constraints:cst_fa_file $KSI_INPUTS/restraints                         \
    -extra_res_fa $KSI_INPUTS/EQU.fa.params                                 \
    -extra_res_cen $KSI_INPUTS/EQU.cen.params                               |
    tee $OUTPUT_PREFIX.log


