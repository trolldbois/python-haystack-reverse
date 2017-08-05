#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

"""Entry points related to reverse. """

import os
import sys

from haystack import argparse_utils
from haystack import cli
from haystack.reverse import api

# the description of the function
REVERSE_DESC = 'Reverse the data structure from the process memory'
REVERSE_SHOW_DESC = 'Show the record at a specific address'
REVERSE_PARENT_DESC = 'List the predecessors pointing to the record at this address'
REVERSE_HEX_DESC = 'Show the Hex values for the record at that address.'


def show_hex(args):
    """ Show the Hex values for the record at that address. """
    memory_handler = cli.make_memory_handler(args)
    process_context = memory_handler.get_reverse_context()
    ctx = process_context.get_context_for_address(args.address)
    try:
        st = ctx.get_record_at_address(args.address)
        print(repr(st.bytes))
    except ValueError as e:
        print(None)
    return


def show_predecessors_cmdline(args):
    """
    Show the predecessors that point to a record at a particular address.
    :param args: cmdline args
    :return:
    """
    memory_handler = cli.make_memory_handler(args)
    process_context = memory_handler.get_reverse_context()
    ctx = process_context.get_context_for_address(args.address)
    try:
        child_record = ctx.get_record_at_address(args.address)
    except ValueError as e:
        print(None)
        return

    records = api.get_record_predecessors(memory_handler, child_record)
    if len(records) == 0:
        print(None)
    else:
        for p_record in records:
            print('#0x%x\n%s\n' % (p_record.address, p_record.to_string()))
    return


def reverse_show_cmdline(args):
    """ Show the record at a specific address. """
    memory_handler = cli.make_memory_handler(args)
    process_context = memory_handler.get_reverse_context()
    ctx = process_context.get_context_for_address(args.address)
    try:
        st = ctx.get_record_at_address(args.address)
        print(st.to_string())
    except ValueError:
        print(None)
    return


def reverse_cmdline(args):
    """ Reverse """
    # get the memory handler adequate for the type requested
    memory_handler = cli.make_memory_handler(args)
    # do the search
    api.reverse_instances(memory_handler)
    return


def reverse():
    argv = sys.argv[1:]
    desc = REVERSE_DESC
    rootparser = cli.base_argparser(program_name=os.path.basename(sys.argv[0]), description=desc)
    rootparser.set_defaults(func=reverse_cmdline)
    opts = rootparser.parse_args(argv)
    # apply verbosity
    cli.set_logging_level(opts)
    # execute function
    opts.func(opts)
    return


def reverse_show():
    argv = sys.argv[1:]
    desc = REVERSE_SHOW_DESC
    rootparser = cli.base_argparser(program_name=os.path.basename(sys.argv[0]), description=desc)
    rootparser.add_argument('address', type=argparse_utils.int16, help='Record memory address in hex')
    rootparser.set_defaults(func=reverse_show_cmdline)
    opts = rootparser.parse_args(argv)
    # apply verbosity
    cli.set_logging_level(opts)
    # execute function
    opts.func(opts)
    return


def reverse_parents():
    argv = sys.argv[1:]
    desc = REVERSE_PARENT_DESC
    rootparser = cli.base_argparser(program_name=os.path.basename(sys.argv[0]), description=desc)
    rootparser.add_argument('address', type=argparse_utils.int16, action='store', default=None,
                            help='Hex address of the child structure')
    rootparser.set_defaults(func=show_predecessors_cmdline)
    opts = rootparser.parse_args(argv)
    # apply verbosity
    cli.set_logging_level(opts)
    # execute function
    opts.func(opts)
    return


def reverse_hex():
    argv = sys.argv[1:]
    desc = REVERSE_HEX_DESC
    rootparser = cli.base_argparser(program_name=os.path.basename(sys.argv[0]), description=desc)
    rootparser.add_argument('address', type=argparse_utils.int16, action='store', default=None,
                            help='Specify the address of the record, or encompassed by the record')
    rootparser.set_defaults(func=show_hex)
    opts = rootparser.parse_args(argv)
    # apply verbosity
    cli.set_logging_level(opts)
    # execute function
    opts.func(opts)
    return
