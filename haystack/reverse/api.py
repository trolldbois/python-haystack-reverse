# -*- coding: utf-8 -*-

from __future__ import print_function
import logging

from haystack.abc import interfaces
from haystack.reverse import config
from haystack.reverse import context
from haystack.reverse.heuristics import reversers
from haystack.reverse.heuristics import dsa
from haystack.reverse.heuristics import pointertypes
from haystack.reverse.heuristics import signature
from haystack.reverse.heuristics import constraints
from haystack.reverse.heuristics import model

log = logging.getLogger('reverse.api')


def reverse_heap(memory_handler, heap_addr):
    """
    Reverse a specific heap.

    :param memory_handler:
    :param heap_addr:
    :return:
    """
    from haystack.reverse import context
    log.info('[+] Loading the memory dump for HEAP 0x%x', heap_addr)
    heap_context = context.get_context_for_address(memory_handler, heap_addr)
    try:
        # decode bytes contents to find basic types.
        log.info('Reversing Fields')
        fr = dsa.FieldReverser(memory_handler)
        fr.reverse_context(heap_context)

        log.info('Fixing Text Fields')
        tfc = dsa.TextFieldCorrection(memory_handler)
        tfc.reverse_context(heap_context)

        # try to find some logical constructs.
        log.info('Reversing DoubleLinkedListReverser')
        # why is this a reverse_context ?
        doublelink = reversers.DoubleLinkedListReverser(memory_handler)
        doublelink.reverse_context(heap_context)
        doublelink.rename_all_lists()

        # save to file
        file_writer = model.WriteRecordToFile(memory_handler, 'reversed.py')
        file_writer.reverse_context(heap_context)

        # etc
    except KeyboardInterrupt as e:
        # except IOError,e:
        log.warning(e)
        log.info('[+] %d structs extracted' % (heap_context.get_record_count()))
        raise e
        pass
    pass
    return heap_context


def reverse_instances(memory_handler):
    """
    Reverse all heaps in process from memory_handler

    1. dsa.FieldReverser
    2. dsa.TextFieldCorrection
    3. reversers.DoubleLinkedListReverser
    4. pointertypes.PointerFieldReverser
    5. save
    6. reversers.PointerGraphReverser
    7. reversers.StringsReverser

    :param memory_handler:
    :return:
    """
    assert isinstance(memory_handler, interfaces.IMemoryHandler)
    process_context = memory_handler.get_reverse_context()
    #for heap in heaps:
    #    # reverse all fields in all records from that heap
    #    ## reverse_heap(memory_handler, heap_addr)

    log.info('Reversing Fields')
    fr = dsa.FieldReverser(memory_handler)
    fr.reverse()

    log.info('Fixing Text Fields')
    tfc = dsa.TextFieldCorrection(memory_handler)
    tfc.reverse()

    # try to find some logical constructs.
    log.info('Reversing DoubleLinkedListReverser')
    # why is this a reverse_context ?
    doublelink = reversers.DoubleLinkedListReverser(memory_handler)
    doublelink.reverse()
    doublelink.rename_all_lists()

    # then and only then can we look at the PointerFields
    # identify pointer relation between allocators
    log.info('Reversing PointerFields')
    pfr = pointertypes.PointerFieldReverser(memory_handler)
    pfr.reverse()

    # save that
    log.info('Saving reversed records instances')
    file_writer = model.WriteRecordToFile(memory_handler, basename='instances.py')
    file_writer.reverse()

    # then we try to match similar record type together
    log.info('Grouping records with a similar signature')
    sig_type_rev = signature.TypeReverser(memory_handler)
    sig_type_rev.reverse()

    # save that
    log.info('Saving reversed records instances with signature')
    file_writer = model.WriteRecordToFile(memory_handler, basename='instances_with_sig.py')
    file_writer.reverse()

    # then we gather the value space of fields for each record, grouped by similar signature
    log.info('Saving reversed records types')
    fvrr = constraints.FieldValueRangeReverser(memory_handler, output_to_file=True)
    fvrr.reverse()

    # graph pointer relations between allocators
    log.info('Reversing PointerGraph')
    ptrgraph = reversers.PointerGraphReverser(memory_handler)
    ptrgraph.reverse()

    # extract all strings
    log.info('Reversing strings')
    strout = reversers.StringsReverser(memory_handler)
    strout.reverse()

    log.info('Analysis results are in %s', config.get_cache_folder_name(memory_handler.get_name()))
    return process_context


def get_record_at_address(memory_handler, record_address):
    """
    Returns the record athe specified address.

    :param memory_handler:
    :param record_address:
    :return:
    """
    heap_context = context.get_context_for_address(memory_handler, record_address)
    return heap_context.get_record_at_address(record_address)


def get_record_predecessors(memory_handler, record):
    """
    Returns the predecessors of this record.

    :param memory_handler:
    :param record:
    :return:
    """
    process_context = memory_handler.get_reverse_context()
    _records = process_context.get_predecessors(record)
    return _records
