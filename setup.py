#!/usr/bin/env python2

from setuptools import setup, find_packages

with open('pull_into_place/__init__.py') as file:
    exec file.read()

with open('README.rst') as file:
    readme = file.read()

def define_command(module, extras=None):
    entry_point = '{0} = pull_into_place.commands.{0}:main'.format(module)
    if extras is not None:
        entry_point += ' {0}'.format(extras)
    return entry_point


setup(
    name='pull_into_place',
    version=__version__,
    author=__author__,
    author_email=__email__,
    url='https://github.com/Kortemme-Lab/pull_into_place',
    download_url='https://github.com/Kortemme-Lab/pull_into_place/tarball/v'+__version__,
    license='GPLv3',
    description="A rosetta pipeline to position important protein sidechains with sub-angstrom accuracy.",
    long_description=readme,
    keywords=[
        'scientific',
        'rosetta',
        'design',
        'protein',
        'sidechain',
    ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 2',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
    ],
    packages=find_packages(),
    package_data={
        'pull_into_place': [
            'big_jobs/*.py',
            'big_jobs/*.xml',
        ],
    },
    install_requires=[
        'klab',
    ],
    extras_require={
        'analysis': [
            'numpy',
            'scipy',
            'pandas',
            'numexpr',
            'matplotlib',
            'show_my_designs',
            'xlsxwriter',
            'pyyaml',
            'sklearn',
            'biopython',
            'weblogo',
        ],
    },
    entry_points={
        'console_scripts': [
            'pull_into_place=pull_into_place.main:main',
        ],
        'pull_into_place.commands': [
            define_command('01_setup_workspace'),
            define_command('02_setup_model_fragments'),
            define_command('03_build_models'),
            define_command('04_pick_models_to_design', '[analysis]'),
            define_command('05_design_models'),
            define_command('06_pick_designs_to_validate', '[analysis]'),
            define_command('06_manually_pick_designs_to_validate'),
            define_command('07_setup_design_fragments'),
            define_command('08_validate_designs'),
            define_command('09_compare_best_designs', '[analysis]'),
            define_command('cache_models', '[analysis]'),
            define_command('count_models', '[analysis]'),
            define_command('fetch_and_cache_models', '[analysis]'),
            define_command('fetch_data'),
            define_command('make_web_logo', '[analysis]'),
            define_command('push_data'),
            define_command('plot_funnels', '[analysis]'),
        ],
    },
)
