#!/usr/bin/env python2

__version__ = '1.2.2'
__author__ = 'Kale Kundert, Cody Krivacic, and Tanja Kortemme'
__email__ = 'kortemme@cgl.ucsf.edu'

# This file is exec'd by setup.py, so we don't want to do anything that would 
# require the package to be installed already.
try:
    from .pipeline import *
except ValueError:  # "Attempted relative import in non-package"
    pass
