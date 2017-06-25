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

    def initialize_options(self):
        """Set default values for options."""
        pass

    def finalize_options(self):
        """Post-process options."""
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
      version="0.41",
      description="Reverse C Structures from a process' memory",
      long_description=open("README.rst").read(),
      url="http://packages.python.org/haystack-reverse/",
      download_url="http://github.com/trolldbois/python-haystack-reverse/tree/master",
      license="GPL",
      classifiers=[
        "Topic :: System :: Networking",
        "Topic :: Security",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        # "Development Status :: 5 - Production/Stable",
      ],
      keywords=["memory", "analysis", "forensics", "record", "struct", "reverse", "heap"],
      author="Loic Jaquemet",
      author_email="loic.jaquemet+python@gmail.com",
      packages=["haystack.reverse",
                "haystack.reverse.heuristics",
      ],
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
      # reverse: install requires networkx, numpy, Levenshtein for signatures
      install_requires=["haystack>=0.41",
                        "numpy",
                        "networkx",
                        "python-Levenshtein"],
      dependency_links=[
                        "https://github.com/trolldbois/python-haystack/tarball/development#egg=haystack",
                        ],
      test_suite="test.alltests",
      cmdclass={
          'preptests': PyPrepTestsCommand,
      },
)

