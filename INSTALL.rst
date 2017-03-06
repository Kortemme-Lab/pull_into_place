************
Installation
************
Typically, you would install Pull Into Place (PIP) both on your workstation and 
on your supercomputing cluster.  On your cluster, you would run the steps in 
the pipeline that involve long rosetta simulations.  On your workstation, you 
would run the analysis and filtering steps between those simulations.  The 
reason for splitting up the work like this is that the analysis scripts have 
more dependencies than the simulation scripts, and those dependencies can be 
hard to install on clusters with limited internet access and/or out-of-date 
software.  Some of the analysis scripts also require a GUI environment, which 
most clusters don't have.  Also note that the simulation scripts require 
``python>=2.6`` while the analysis scripts require ``python>=2.7``.

.. note::
   Right now, the pipeline will only work as written on the QB3 cluster at 
   UCSF.  There are two issues preventing more general use.  The first issue is 
   that all of the scripts that submit jobs to the cluster use Sun Grid Engine 
   (SGE) commands to do so.  This would be easy to generalize, but so far there 
   hasn't been any need to do so.  If you have a need, send an email to the 
   maintainer describing your system and we'll do what we can to support it. 
   
   The second issue is that the fragment generation scripts contain a number of 
   hard-coded paths to executables and databases that are specific to the QB3 
   cluster.  For a variety of reasons, fixing this would be a fairly serious 
   undertaking.  Nonetheless, please let the maintainer know if you need this 
   done, and we'll do what we can.  In the meantime, you can try using 
   simulations that don't require fragments (although these don't perform as 
   well) or generating fragments yourself.
   
Installing PIP on your workstation
==================================
PIP is available on PyPI, so you can use ``pip`` to install it.  (Sorry if the 
distinction between PIP and ``pip`` is confusing.  PIP is the Pull Into Place 
pipeline, ``pip`` is the package manager distributed with modern versions of 
python)::

   $ pip install 'pull_into_place [analysis]'

The ``[analysis]`` part of the command instructs ``pip`` to install all of the 
dependencies for the analysis scripts.  These dependencies aren't installed by 
default because they aren't needed for the rosetta simulation steps and they 
can be challenging to install on some clusters.

If the installation worked, this command should print out a nice help message::

   $ pull_into_place --help

.. note::
   If you don't have administrator access on your workstation, or if you just 
   don't want to install PIP system-wide, you can use the ``--user`` flag to 
   install PIP in your home directory::

      $ pip install 'pull_into_place [analysis]' --user

   This will install the PIP executable in ``~/.local/bin``, which may not be 
   on your ``$PATH`` by default.  If the installation seemed to work but you 
   get a "command not found" error when trying to run ``pull_into_place``, you 
   probably need to add ``~/.local/bin`` to ``$PATH``::

      echo 'export PATH=~/.local/bin:$PATH' >> ~/.bashrc
      source ~/.bashrc

GTK and the ``plot_funnels`` command
------------------------------------
The ``plot_funnels`` command creates an interactive GUI that can show score vs 
RMSD funnels, open structures corresponding to individual points in ``pymol`` 
or ``chimera``, and keep track of your notes on different designs.  

In order to use this command, you have to install ``pygtk`` yourself.  This 
dependency is not included with the other ``[analysis]`` dependencies because 
it can't be installed with ``pip`` (except maybe on Windows).  On Linux 
systems, your package manager should be able to install it pretty easily::

   $ apt-get install pygtk  # Ubuntu
   $ yum install pygtk2     # Fedora<=21
   $ dnf install pygtk2     # Fedora>=22

On Mac systems, the easiest way to do this is to use ``homebrew`` to install 
``matplotlib`` with the ``--with-pygtk`` option::

   $ brew install matplotlib --with-pygtk

Installing PIP on your cluster
==============================
If ``pip`` is available on your cluster, use it::

   $ pip install pull_into_place

Otherwise, you will need to install PIP manually.  The first step is to 
download and install source distributions of |setuptools|_ and |klab|_.  PIP 
needs |setuptools|_ to install itself and |klab|_ to access a number of 
general-purpose tools developed by the Kortemme lab.  Once those dependencies 
are installed, you can download and install a source distribution of 
|pull_into_place|_.  The next section has example command lines for all of 
these steps in the specific context of the QB3 cluster at UCSF.

Installing PIP on the QB3 cluster at UCSF
-----------------------------------------
Because the UCSF cluster is not directly connected to the internet, it cannot 
automatically download and install dependencies.  Instead, we have to do these 
steps manually.

1. Download the most recent source distributions for |setuptools|_, |klab|_, 
   and |pull_into_place|_ from PyPI (those are links, in case it's hard to 
   tell) onto your workstation.  When I did this, the most recent distributions 
   were:
   
   - ``setuptools-27.2.0.tar.gz``
   - ``klab-0.3.0.tar.gz``
   - ``pull_into_place-1.2.0.tar.gz``
   |
   .. note::
      Three new dependencies were added to ``setuptools`` in version 
      ``34.0.0``: ``six``, ``packaging``, and ``appdirs``.  You can either 
      install these dependencies in the same way as the others, or you can just 
      use an earlier version of setuptools.

2. Copy the source distributions onto the cluster::

   $ scp setuptools-27.2.0.tar.gz chef.compbio.ucsf.edu:
   $ scp klab-0.3.0.tar.gz chef.compbio.ucsf.edu:
   $ scp pull_into_place-1.2.0.tar.gz chef.compbio.ucsf.edu:

3. Log onto the cluster and unpack the source distributions::

   $ ssh chef.compbio.ucsf.edu
   $ tar -xzf setuptools-27.2.0.tar.gz
   $ tar -xzf klab-0.3.0.tar.gz
   $ tar -xzf pull_into_place-1.2.0.tar.gz

4. Install |setuptools|_::

   $ cd ~/setuptools-27.2.0
   $ python setup.py install --user

5. Install |klab|_::

   $ cd ~/klab-0.3.0
   $ python setup.py install --user

6. Install |pull_into_place|_::

   $ cd ~/pull_into_place-1.2.0
   $ python setup.py install --user

7. Make sure ``~/.local/bin`` is on your ``$PATH``::

   The above commands install PIP into ``~/.local/bin``.  This directory is 
   good because you can install programs there without needing administrator 
   privileges, but it's not on your ``$PATH`` by default (which means that any 
   programs installed there won't be found).  This command modifies your shell 
   configuration file to add ``~/.local/bin`` to your ``$PATH``::

       $ echo 'export PATH=~/.local/bin:$PATH' >> ~/.bashrc

   This command reloads your shell configuration so the change takes place 
   immediately (otherwise you'd have to log out and back in)::

       $ source ~/.bashrc

7. Make sure it works::

   $ pull_into_place --help

.. |setuptools| replace:: ``setuptools``
.. _setuptools: https://pypi.python.org/pypi/setuptools
.. |klab| replace:: ``klab``
.. _klab: https://pypi.python.org/pypi/klab
.. |pull_into_place| replace:: ``pull_into_place``
.. _pull_into_place: https://pypi.python.org/pypi/pull_into_place

.. _installing-rosetta:

Installing Rosetta
==================
PIP also requires Rosetta to be installed, both on your workstation and on your 
cluster.  You can consult `this page`__ for more information on how to do this, 
but in general there are two steps.  First, you need to check out a copy of the 
source code from GitHub::

    $ git clone git@github.com:RosettaCommons/main.git ~/rosetta

Second, you need to compile everything::

    $ cd ~/rosetta/source
    $ ./scons.py bin mode=release -j8

Be aware that compiling Rosetta requires a C++11 compiler.  This is much more 
likely to cause problems on your cluster than on your workstation.  If you have 
problems, ask your administrator for help.

__ https://www.rosettacommons.org/docs/latest/build_documentation/Build-Documentation

Installing Rosetta on the QB3 cluster at UCSF
---------------------------------------------
Installing Rosetta on the QB3 cluster is especially annoying because the 
cluster has limited access to the internet and outdated versions of both the 
C++ compiler and python.  As above, the first step is to check out a copy of 
the Rosetta source code from GitHub.  This has to be done from one of the 
interactive nodes (e.g. ``iqint``, ``optint1``, ``optint2``, or ``xeonint``) 
because ``chef`` and ``sous`` are not allowed to communicate with GitHub::

    $ ssh chef.compbio.ucsf.edu
    $ ssh iqint
    $ git clone git@github.com:RosettaCommons/main.git ~/rosetta

The second step is to install the QB3-specific build settings, which specify 
the path to the cluster's C++11 compiler (among other things)::

    $ ln -s site.settings.qb3 ~/rosetta/source/tools/build/site.settings

The final step is to compile Rosetta.  This command has several parts: ``scl 
enable python27`` causes python2.7 to be used for the rest of the command, 
which ``scons`` requires.  ``nice`` reduces the compiler's CPU priority, which 
helps the shell stay responsive.  ``./scons.py bin`` is the standard command to 
build Rosetta.  ``mode=release`` tells to compiler to leave out debugging code, 
which actually makes Rosetta ≈10x faster.  ``-j16`` tells the compiler that 
``iqint`` has 16 cores for it to use::

    $ cd ~/rosetta/source
    $ scl enable python27 'nice ./scons.py bin mode=release -j16'

