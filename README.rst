python-haystack-reverse memory forensics
########################################

|travis| |coverage| |landscape| |pypi|

Quick Start:
============
`Haystack-reverse CLI <docs/Haystack_reverse_CLI.ipynb>`_ in the docs/ folder.


Introduction:
=============

python-haystack-reverse is extension of `python-haystack <https://github.com/trolldbois/python-haystack>`_ focused on
reversing memory structure in allocated memory.

It aims at helping an analyst in reverse engineering the memory records types present in a process heap.
It focuses on reconstruction, classification of classic C structures from memory.
It attempts to recreate types definition.

Scripts & Entry Points:
=======================

A few entry points exists to handle the format your memory dump.

Memory dump folder produced by ``haystack-live-dump`` from the haystack package
-------------------------------------------------------------------------------
 - ``haystack-reverse`` reverse CLI - reverse all allocation chunks
 - ``haystack-reverse-show`` show the reversed record at a specific address
 - ``haystack-reverse-hex`` show a specific record hex bytes at a specific address
 - ``haystack-reverse-parents`` show the records pointing to the allocated record at a specific address

Memory dump file produced by a Minidump tool
--------------------------------------------
 - ``haystack-minidump-reverse`` reverse CLI - reverse all allocation chunks
 - ``haystack-minidump-reverse-show`` show the reversed record at a specific address
 - ``haystack-minidump-reverse-hex`` show a specific record hex bytes at a specific address
 - ``haystack-minidump-reverse-parents`` show the records pointing to the allocated record at a specific address

How to get a memory dump:
=========================

See `python-haystack <https://github.com/trolldbois/python-haystack>`_ or use Sysinternals procdump.

Heap analysis / forensics:
==========================

Quick info:
 - The ``haystack-xxx-reverse`` family of entry points parse the heap for allocator structures,
pointers values, small integers and text (ascii/utf).
Given all the previous information, it can extract instances and helps you
in classifying and defining structures types.

IPython notebook usage guide:
 - `Haystack-reverse CLI <docs/Haystack_reverse_CLI.ipynb>`_ in the docs/ folder.

Command line example:
--------------------_
The first step is to launch the analysis process with the ``haystack-xxx-reverse`` entry point.
This will create several files in the ``cache/`` folder in the memory dump folder:

.. code-block:: bash

    $ haystack-reverse haystack/test/src/test-ctypes6.64.dump
    $ ls -l haystack/test/src/test-ctypes6.64.dump/cache
    $ ls -l haystack/test/src/test-ctypes6.64.dump/cache/structs

This will create a few files. The most interesting one being the ``<yourdumpfolder>/cache/xxxxx.headers_values.py`` that
gives you an ctypes listing of all found structures, with guesstimates
on fields types.

A ``<yourdumpfolder>/cache/graph.gexf`` file is also produced to help you visualize
instances links. It gets messy for any kind of serious application.

- ``*.headers_values.py`` contains the list of heuristicly reversed record types.
- ``*.strings`` contains the list of heuristicly typed strings field in reversed record.

Other Entry points for reversing:
---------------------------------

 - ``haystack-reverse-show`` show a specific record at a specific address
 - ``haystack-reverse-hex`` show a specific record hex bytes at a specific address
 - ``haystack-reverse-parents`` show the records pointing to the allocated record at a specific address
 - ``haystack-minidump-reverse-show`` show a specific record at a specific address
 - ``haystack-minidump-reverse-hex`` show a specific record hex bytes at a specific address
 - ``haystack-minidump-reverse-parents`` show the records pointing to the allocated record at a specific address


Dependencies:
-------------

- haystack
- python-numpy
- python-networkx
- python-levenshtein
- several others...



.. |pypi| image:: https://img.shields.io/pypi/v/haystack-reverse.svg?style=flat-square&label=latest%20stable%20version
    :target: https://pypi.python.org/pypi/haystack-reverse
    :alt: Latest version released on PyPi

.. |coverage| image:: https://img.shields.io/coveralls/trolldbois/python-haystack-reverse/master.svg?style=flat-square&label=coverage
    :target: https://coveralls.io/github/trolldbois/python-haystack-reverse?branch=master
    :alt: Test coverage

.. |travis| image:: https://img.shields.io/travis/trolldbois/python-haystack-reverse/master.svg?style=flat-square&label=travis-ci
    :target: http://travis-ci.org/trolldbois/python-haystack-reverse
    :alt: Build status of the master branch on Mac/Linux

.. |landscape| image:: https://landscape.io/github/trolldbois/python-haystack-reverse/master/landscape.svg?style=flat
   :target: https://landscape.io/github/trolldbois/python-haystack-reverse/master
   :alt: Code Health
