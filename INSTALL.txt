Installation
============
Install the Pull Into Place pipeline using ``pip``::

    $ pip install pull_into_place

This command won't install any of the dependencied need by the analysis 
scripts, because the rest of the scripts 

Installation on the UCSF Cluster
================================
Installing PIP requires ``setuptools``, which is not present by default on the 
cluster.  To install it, you need to download the most recent ``setuptools`` 
source distribution from ``https://pypi.python.org/pypi/setuptools``.  When I 
did this, the most recent distribution was ``setuptools-27.2.0.tar.gz``.  Then 
run the following commands to copy the setuptools onto the cluster and to 
install it::
    
    $ scp setuptools-27.2.0.tar.gz chef.compbio.ucsf.edu:
    $ ssh chef.compbio.ucsf.edu
    $ tar -xzf setuptools-27.2.0.tar.gz
    $ cd setuptools-27.2.0
    $ python setup.py install --user

PIP also requires ``klab``, the Kortemme Lab 

---

Installation
============
Install the Pull Into Place pipeline by cloning its git repository with the 
following command.  The --recursive option tells git to also clone the 'tools' 
submodule used by PIP.

$ git clone --recursive https://guybrush.ucsf.edu/gitlab/kortemme-lab/pull_into_place.git

If you are cloning PIP on the UCSF cluster and are using the Kortemme lab's SSH 
tunneling tricks, then you can't use the command above because it will crash 
when it tries to clone the 'tools' submodule without going through a tunnel.  
Instead, use this set of commands to install PIP::

$ git clone git@gitlab:kortemme-lab/pull_into_place.git
$ cd pull_into_place
$ git submodule init
$ vim .git/config   

In the editor, change the lines that say:
    
[submodule "tools"]
    url = git@guybrush.ucsf.edu:kortemme-lab/tools.git

to:
    
[submodule "tools"]
    url = git@gitlab:kortemme-lab/tools.git

where 'gitlab' is the name of your tunnel to guybrush.ucsf.edu on port 22.  The 
save, exit, and run one last command to clone the 'tools' submodule:

$ git submodule update

Dependencies
============
In general, there are two types of scripts in this pipeline: those that run on 
the cluster and those that analyze results.  The cluster scripts don't require 
anything beyond Sun Grid Engine (SGE) and the python 2.6 standard distribution.  
The analysis scripts typically require python 2.7 and the full complement of 
scientific python packages.  The view_models.py script additionally requires 
the Gtk2 GUI library, which is often pre-installed on Linux and is probably 
possible to install on other systems as well.  All the packages needed to run 
the analysis scripts are listed below:

python 2.7
numpy 1.9
scipy 0.12
pandas 0.15
numexpr 2.2
matplotlib 1.3
pygtk 2.24
xlsxwriter 0.5
pyyaml 3.1

python-tk
