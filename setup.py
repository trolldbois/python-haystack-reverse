#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Setuptools scripts."""

from setuptools import setup

import distutils.cmd
import distutils.log
import subprocess
import sys


class PyPrepTestsCommand(distutils.cmd.Command):
    """
    A custom command to build test sets.
    Requires ctypeslib2.
    """

    description = 'Run tests and dumps memory'
    user_options = []
    #    # The format is (long option, short option, description).
    #    ('pylint-rcfile=', None, 'path to Pylint _target_platform file'),
    # ]

    def initialize_options(self):
        """Set default values for options."""
    #  # Each user option must be listed here with their default value.
    #  self.pylint_rcfile = ''
        pass

    def finalize_options(self):
        """Post-process options."""
    #  if self.pylint_rcfile:
    #    assert os.path.exists(self.pylint_rcfile), (
    #        'Pylint _target_platform file %s does not exist.' % self.pylint_rcfile)
        pass

    def run(self):
        """Run command."""
        import os
        import sys
        os.getcwd()
        # all dump files are in .tgz
        makeCmd = ['make', '-d']
        p = subprocess.Popen(makeCmd, stdout=sys.stdout, cwd='test/src/')
        p.wait()
        return p.returncode


setup(name="haystack-reverse",
      version="0.40",
      description="Reverse C Structures from a process' memory",
      long_description=open("README.md").read(),
      url="http://packages.python.org/haystack/",
      download_url="http://github.com/trolldbois/python-haystack/tree/master",
      license="GPL",
      classifiers=[
        "Topic :: System :: Networking",
        "Topic :: Security",
        "Environment :: Console",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        # "Development Status :: 5 - Production/Stable",
      ],
      keywords=["memory", "analysis", "forensics", "record", "struct", "ptrace", "reverse", "heap", "lfh", "lal"],
      author="Loic Jaquemet",
      author_email="loic.jaquemet+python@gmail.com",
      packages=[
                "haystack.reverse",
                "haystack.reverse.heuristics",
],
      # package_dir={"haystack.reverse": 'haystack/reverse'},
      package_data={"haystack.reverse.heuristics": ['data/words.100'],},
      entry_points={
          'console_scripts': [
              'haystack-reverse = haystack.reverse.cli:main_reverse',
              'haystack-minidump-reverse = haystack.reverse.cli:minidump_reverse',
              'haystack-reverse-show = haystack.reverse.cli:main_reverse_show',
              'haystack-reverse-parents = haystack.reverse.cli:main_reverse_parents',
              'haystack-reverse-hex = haystack.reverse.cli:main_reverse_hex',
              'haystack-minidump-reverse-show = haystack.reverse.cli:minidump_reverse_show',
              'haystack-minidump-reverse-parents = haystack.reverse.cli:minidump_reverse_parents',
              'haystack-minidump-reverse-hex = haystack.reverse.cli:minidump_reverse_hex',
          ]
      },
      # reverse: numpy is a dependency for reverse.
      # https://github.com/numpy/numpy/issues/2434
      # numpy is already installed in travis-ci
      # setup_requires=["numpy"],
      # search: install requires only pefile, python-ptrace for memory-dump
      # reverse: install requires networkx, numpy, Levenshtein for signatures
      install_requires=[ "haystack",
                        # reverse need these.
                        # "numpy",
                        "networkx",
                        "python-Levenshtein"],
      dependency_links=[
                        # "https://github.com/trolldbois/ctypeslib/tarball/dev#egg=ctypeslib2-2.4beta",
                        "https://github.com/volatilityfoundation/volatility/tarball/master#egg=volatility-trunk",
                        "https://github.com/google/rekall/tarball/master#egg=rekall-trunk",
                        "https://github.com/erocarrera/pefile/archive/pefile-1.2.10-139.tar.gz"],
      # build_test_requires = ["ctypeslib2>=2.1.3"],
      test_suite="test.alltests",
      # https://pythonhosted.org/setuptools/setuptools.html
      # prep_test requires ctypeslib2
      # tests_require=["volatility"],
      # tests_require=["ctypeslib2>2.1.3"],
      cmdclass={
          'preptests': PyPrepTestsCommand,
      },
)

