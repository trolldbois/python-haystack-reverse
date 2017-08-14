#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import itertools
import logging
import os
import re
import struct

import Levenshtein  # seqmatcher ?
import networkx
import numpy
from haystack.utils import xrange

import haystack.reverse.matchers
from haystack.reverse import config
from haystack.reverse import searchers
from haystack.reverse import utils
from haystack.reverse.heuristics import model

"""
Tools around guessing a field' type and
creating signature for record to compare them.
"""


log = logging.getLogger('signature')


class TypeReverser(model.AbstractReverser):
    """
    Goal is to find similar types, using signatures from previous heuristics.
    And to rename similar typed records.

    Abstract Reverser, that do not go to the record level (except to get a signature).

    1. Look at all record type signatures.
    2. Compare all signatures together using Levenshtein
    3. Group records with similar signature together, in a graph
    4. Rename record types for similar records

    """
    REVERSE_LEVEL = 300

    def __init__(self, memory_handler):
        super(TypeReverser, self).__init__(memory_handler)
        self._signatures = None
        self._similarities = None
        try:
            import pkgutil
            self._words = pkgutil.get_data(__name__, config.WORDS_FOR_REVERSE_TYPES_FILE).decode()
        except ImportError:
            import pkg_resources
            self._words = pkg_resources.resource_string(__name__, config.WORDS_FOR_REVERSE_TYPES_FILE).decode()

        self._NAMES = [s.strip() for s in self._words.split('\n')[:-1]]
        self._NAMES_plen = 1

    def reverse_context(self, _context):
        """
        Go over each record and call the reversing process.
        """
        log.info('[+] %s: START on heap 0x%x', self, _context._heap_start)
        signatures = self._gather_signatures(_context)
        similarities = self._chain_similarities(signatures)
        self._rename_similar_records(self._memory_handler.get_reverse_context(), _context, similarities)
        # just tag the records
        for _record in _context.listStructures():
            self.reverse_record(_context, _record)
        _context.save()
        return

    def reverse_record(self, _context, _record):
        # TODO: add minimum reversing level check before running
        # if _record.get_reverse_level() < 30:
        #     raise RuntimeError("Please reverse records before calling this")
        _record.set_reverse_level(self._reverse_level)
        return

    def _gather_signatures(self, _context):
        log.debug("Gathering all signatures")
        signatures = []
        for _record in _context.listStructures():
            signatures.append((len(_record), _record.address, _record.get_signature_text()))
            self._nb_reversed += 1
            self._callback(total=1)  # FIXME total should not be 1.
        # order by size
        signatures.sort()
        return signatures

    def _chain_similarities(self, signatures):
        similarities = []
        for i, (size1, addr1, el1) in enumerate(signatures[:-1]):
            log.debug("Comparing signatures with %s", el1)
            for size2, addr2, el2 in signatures[i + 1:]:
                # if abs(size1 - size2) > 4*self._word_size:
                #     continue
                # RULE - records with different size are not similar
                if size2 != size1:
                    break
                lev = Levenshtein.ratio(el1, el2)  # seqmatcher ?
                if lev > 0.75:
                    similarities.append((addr1, addr2))
                    # we do not need the signature.
        # proposition to the user
        log.debug('\t[-] Signatures done. %d similar couples.' % len(similarities))
        graph = networkx.Graph()
        graph.add_edges_from(similarities)
        subgraphs = networkx.algorithms.components.connected.connected_component_subgraphs(graph)
        chains = [g.nodes() for g in subgraphs]
        for c in chains:
            log.debug(c)
        return chains

    def _make_original_type_name(self):
        # refill the pool if empty
        if len(self._NAMES) == 0:
            self._NAMES_plen += 1
            self._NAMES = [''.join(x) for x in itertools.permutations(self._words.split('\n')[:-1], self._NAMES_plen)]
        return self._NAMES.pop()

    def _rename_similar_records(self, process_context, heap_context, chains):
        """ Fix the name of each structure to a generic word/type name """
        # order chains by size of records
        # which produce nearly a stable resolution system.
        chains.sort(key=lambda x: len(x))
        for chain in chains:
            name = self._make_original_type_name()
            log.debug('\t[-] fix type of chain size:%d with name:%s %s' % (len(chain), name, chain))
            # FIXME : actually choose the best reference type by checking connectivity in graph ?
            reference_type = heap_context.get_record_for_address(chain[0]).record_type
            reference_type.type_name = name
            for addr in chain:  # chain is a list of addresses
                instance = heap_context.get_record_for_address(addr)
                instance.name = name
                # we change the record type on all instance
                instance.set_record_type(reference_type)
        return


class CommonTypeReverser(model.AbstractReverser):
    """
    From a list of records addresse, find the most common signature.
    """
    REVERSE_LEVEL = 31

    def __init__(self, memory_handler, members):
        super(CommonTypeReverser, self).__init__(memory_handler)
        self._members = members
        self._members_by_context = {}
        process_context = self._memory_handler.get_reverse_context()
        # organise the list
        for record_addr in self._members:
            heap_context = process_context.get_context_for_address(record_addr)
            if heap_context not in self._members_by_context:
                self._members_by_context[heap_context] = []
            self._members_by_context[heap_context].append(record_addr)
        # out
        self._signatures = {}
        self._similarities = []

    def _iterate_contexts(self):
        for c in self._members_by_context.keys():
            yield c

    def _iterate_records(self, _context):
        for item_addr in self._members_by_context[_context]:
            yield _context.get_record_for_address(item_addr)

    def reverse_record(self, _context, _record):
        record_signature = _record.get_signature_text()
        if record_signature not in self._signatures:
            self._signatures[record_signature] = []
        self._signatures[record_signature].append(_record.address)

    def calculate(self):
        #
        res = [(len(v), k) for k,v in self._signatures.items()]
        res.sort(reverse=True)
        total = len(self._members)
        best_count = res[0][0]
        best_sig = res[0][1]
        best_addr = self._signatures[best_sig][0]
        log.debug('best match %d/%d is %s: 0x%x', best_count, total, best_sig, best_addr)
        return best_sig, best_addr


class StructureSizeCache:

    """Loads allocators, get their signature (and size) and sort them in
    fast files dictionaries."""

    def __init__(self, ctx):
        self._context = ctx
        self._sizes = None

    def _loadCache(self):
        outdir = config.get_cache_filename(
            config.CACHE_SIGNATURE_SIZES_DIR,
            self._context.dumpname)
        fdone = os.path.sep.join(
            [outdir, config.CACHE_SIGNATURE_SIZES_DIR_TAG])
        if not os.access(fdone, os.R_OK):
            return False
        for myfile in os.listdir(outdir):
            try:
                # FIXME: not sure its -
                # and what that section is about in general.
                addr = int(myfile.split('-')[1], 16)
            except IndexError as e:
                continue  # ignore file

    def cacheSizes(self):
        """Find the number of different sizes, and creates that much numpyarray"""
        # if not os.access
        outdir = config.get_cache_filename(
            config.CACHE_SIGNATURE_SIZES_DIR,
            self._context.dumpname)
        config.create_cache_folder(outdir)
        #
        sizes = map(int, set(self._context._malloc_sizes))
        arrays = dict([(s, []) for s in sizes])
        # sort all addr in all sizes..
        [arrays[self._context._malloc_sizes[i]].append(
            long(addr)) for i, addr in enumerate(self._context._malloc_addresses)]
        # saving all sizes dictionary in files...
        for size, lst in arrays.items():
            fout = os.path.sep.join([outdir, 'size.%0.4x' % size])
            arrays[size] = utils.int_array_save(fout, lst)
        # saved all sizes dictionaries.
        # tag it as done
        open(
            os.path.sep.join([outdir, config.CACHE_SIGNATURE_SIZES_DIR_TAG]), 'w')
        self._sizes = arrays
        return

    def getStructuresOfSize(self, size):
        if self._sizes is None:
            self.cacheSizes()
        if size not in self._sizes:
            return []
        return numpy.asarray(self._sizes[size])

    def __iter__(self):
        if self._sizes is None:
            self.cacheSizes()
        for size in self._sizes.keys():
            yield (size, numpy.asarray(self._sizes[size]))


class SignatureMaker(searchers.AbstractSearcher):
    """
    make a condensed signature of the mapping.
    We could then search the signature file for a specific signature
    """

    NULL = 0x1
    POINTER = 0x2
    # POINTERS = NULL | POINTER # null can be a pointer value so we can
    # byte-test that
    OTHER = 0x4

    def __init__(self, mapping):
        searchers.AbstractSearcher.__init__(self, mapping)
        self.pSearch = haystack.reverse.matchers.PointerSearcher(self.get_search_mapping())
        self.nSearch = haystack.reverse.matchers.NullSearcher(self.get_search_mapping())

    def test_match(self, vaddr):
        ''' return either NULL, POINTER or OTHER '''
        if self.nSearch.test_match(vaddr):
            return self.NULL
        if self.pSearch.test_match(vaddr):
            return self.POINTER
        return self.OTHER

    def search(self):
        ''' returns the memspace signature. Dont forget to del that object, it's big. '''
        self._values = b''
        log.debug(
            'search %s mapping for matching values' %
            (self.get_search_mapping()))
        for vaddr in xrange(
                self.get_search_mapping().start, self.get_search_mapping().end, self.WORDSIZE):
            self._check_steps(vaddr)  # be verbose
            self._values += struct.pack('B', self.test_match(vaddr))
        return self._values

    def __iter__(self):
        ''' Iterate over the mapping to return the signature of that memspace '''
        log.debug(
            'iterate %s mapping for matching values' %
            (self.get_search_mapping()))
        for vaddr in xrange(
                self.get_search_mapping().start, self.get_search_mapping().end, self.WORDSIZE):
            self._check_steps(vaddr)  # be verbose
            yield struct.pack('B', self.test_match(vaddr))
        return


class PointerSignatureMaker(SignatureMaker):

    def test_match(self, vaddr):
        ''' return either POINTER or OTHER '''
        if self.pSearch.test_match(vaddr):
            return self.POINTER
        return self.OTHER


class RegexpSearcher(searchers.AbstractSearcher):

    '''
    Search by regular expression in memspace.
    '''

    def __init__(self, mapping, regexp):
        searchers.AbstractSearcher.__init__(self, mapping)
        self.regexp = regexp
        self.pattern = re.compile(regexp, re.IGNORECASE)

    def search(self):
        ''' find all valid matches offsets in the memory space '''
        self._values = set()
        log.debug(
            'search %s mapping for matching values %s' %
            (self.get_search_mapping(), self.regexp))
        for match in self.get_search_mapping().finditer(
                self.get_search_mapping().mmap().get_byte_buffer()):
            offset = match.start()
            # FIXME, TU what is value for?
            value = match.group(0)
            if isinstance(value, list):
                value = ''.join([chr(x) for x in match.group()])
            vaddr = offset + self.get_search_mapping().start
            self._check_steps(vaddr)  # be verbose
            self._values.add((vaddr, value))
        return self._values

    def __iter__(self):
        ''' Iterate over the mapping to find all valid matches '''
        log.debug(
            'iterate %s mapping for matching values' %
            (self.get_search_mapping()))
        for match in self.pattern.finditer(
                self.get_search_mapping().mmap().get_byte_buffer()):
            offset = match.start()
            value = match.group(0)  # [] of int ?
            if isinstance(value, list):
                value = ''.join([chr(x) for x in match.group()])
            vaddr = offset + self.get_search_mapping().start
            self._check_steps(vaddr)  # be verbose
            yield (vaddr, value)
        return

    def test_match(self, vaddr):
        return True

#EmailRegexp = r'''[a-zA-Z0-9+_\-\.]+@[0-9a-zA-Z][.-0-9a-zA-Z]*.[a-zA-Z]+'''
EmailRegexp = r'''((\"[^\"\f\n\r\t\v\b]+\")|([\w\!\#\$\%\&\'\*\+\-\~\/\^\`\|\{\}]+(\.[\w\!\#\$\%\&\'\*\+\-\~\/\^\`\|\{\}]+)*))@((\[(((25[0-5])|(2[0-4][0-9])|([0-1]?[0-9]?[0-9]))\.((25[0-5])|(2[0-4][0-9])|([0-1]?[0-9]?[0-9]))\.((25[0-5])|(2[0-4][0-9])|([0-1]?[0-9]?[0-9]))\.((25[0-5])|(2[0-4][0-9])|([0-1]?[0-9]?[0-9])))\])|(((25[0-5])|(2[0-4][0-9])|([0-1]?[0-9]?[0-9]))\.((25[0-5])|(2[0-4][0-9])|([0-1]?[0-9]?[0-9]))\.((25[0-5])|(2[0-4][0-9])|([0-1]?[0-9]?[0-9]))\.((25[0-5])|(2[0-4][0-9])|([0-1]?[0-9]?[0-9])))|((([A-Za-z0-9\-])+\.)+[A-Za-z\-]+))'''
URLRegexp = r'''[a-zA-Z0-9]+://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'''
# URIRegexp =
# r'''#^([a-z0-9+\-.]+):([/]{0,2}([a-z0-9\-._~%!\$&'\(\)\*+,;=:]+@)?([\[\]a-z0-9\-._~%!\$&'\(\)\*+,;=:]+(:[0-9]+)?))([a-z0-9\-._~%!\$&'\(\)\*+,;=:@/]*)(\?[\?/a-z0-9\-._~%!\$&'\(\)\*+,;=:@]+)?(\#[a-z0-9\-._~%!\$&'\(\)\*+,;=:@/\?]+)?#i'''
WinFileRegexp = r'''([a-zA-Z]\:)(\\[^\\/:*?<>"|]*(?<![ ]))*(\.[a-zA-Z]{2,6})'''
#WinFileRegexp = r'''(.*?)([^/\\]*?)(\.[^/\\.]*)?'''
IPv4Regexp = r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'''
IPv6Regexp = r'''(::|(([a-fA-F0-9]{1,4}):){7}(([a-fA-F0-9]{1,4}))|(:(:([a-fA-F0-9]{1,4})){1,6})|((([a-fA-F0-9]{1,4}):){1,6}:)|((([a-fA-F0-9]{1,4}):)(:([a-fA-F0-9]{1,4})){1,6})|((([a-fA-F0-9]{1,4}):){2}(:([a-fA-F0-9]{1,4})){1,5})|((([a-fA-F0-9]{1,4}):){3}(:([a-fA-F0-9]{1,4})){1,4})|((([a-fA-F0-9]{1,4}):){4}(:([a-fA-F0-9]{1,4})){1,3})|((([a-fA-F0-9]{1,4}):){5}(:([a-fA-F0-9]{1,4})){1,2}))'''
SQLRegexp = r'''(SELECT\s[\w\*\)\(\,\s]+\sFROM\s[\w]+)| (UPDATE\s[\w]+\sSET\s[\w\,\'\=]+)| (INSERT\sINTO\s[\d\w]+[\s\w\d\)\(\,]*\sVALUES\s\([\d\w\'\,\)]+)| (DELETE\sFROM\s[\d\w\'\=]+)'''
CCardRegexp = r'''((4\d{3})|(5[1-5]\d{2}))(-?|\040?)(\d{4}(-?|\040?)){3}|^(3[4,7]\d{2})(-?|\040?)\d{6}(-?|\040?)\d{5}'''
SSNRegexp = r'''\d{3}-\d{2}-\d{4}'''
GUIDRegexp = r'''([A-Fa-f0-9]{32}| [A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}| \{[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}\})'''
# UNCRegexp = r'''((\\\\[a-zA-Z0-9-]+\\[a-zA-Z0-9`~!@#$%^&(){}'._-]+([ ]+[a-zA-Z0-9`~!@#$%^&(){}'._-]+)*)|([a-zA-Z]:))(\\[^ \\/:*?""<>|]+([ ]+[^ \\/:*?""<>|]+)*)*\\?'''
#UNCRegexp = r'(([a-zA-Z]:|\\)\\)?(((\.)|(\.\.)|([^\\/:\*\?"\|<>\. ](([^\\/:\*\?"\|<>\. ])|([^\\/:\*\?"\|<>]*[^\\/:\*\?"\|<>\. ]))?))\\)*[^\\/:\*\?"\|<>\. ](([^\\/:\*\?"\|<>\. ])|([^\\/:\*\?"\|<>]*[^\\/:\*\?"\|<>\. ]))?'


def looksLikeUTF8(bytearray):
    p = re.compile("\\A(\n" +
                   r"  [\\x09\\x0A\\x0D\\x20-\\x7E]             # ASCII\\n" +
                   r"| [\\xC2-\\xDF][\\x80-\\xBF]               # non-overlong 2-byte\n" +
                   r"|  \\xE0[\\xA0-\\xBF][\\x80-\\xBF]         # excluding overlongs\n" +
                   r"| [\\xE1-\\xEC\\xEE\\xEF][\\x80-\\xBF]{2}  # straight 3-byte\n" +
                   r"|  \\xED[\\x80-\\x9F][\\x80-\\xBF]         # excluding surrogates\n" +
                   r"|  \\xF0[\\x90-\\xBF][\\x80-\\xBF]{2}      # planes 1-3\n" +
                   r"| [\\xF1-\\xF3][\\x80-\\xBF]{3}            # planes 4-15\n" +
                   r"|  \\xF4[\\x80-\\x8F][\\x80-\\xBF]{2}      # plane 16\n" +
                   r")*\\z", re.VERBOSE)

    phonyString = bytearray.encode("ISO-8859-1")
    return p.matcher(phonyString).matches()

'''
lib["email"] = re.compile(r"(?:^|\s)[-a-z0-9_.]+@(?:[-a-z0-9]+\.)+[a-z]{2,6}(?:\s|$)",re.IGNORECASE)
lib["postcode"] = re.compile("[a-z]{1,2}\d{1,2}[a-z]?\s*\d[a-z]{2}",re.IGNORECASE)
lib["zipcode"] = re.compile("\d{5}(?:[-\s]\d{4})?")
lib["ukdate"] = re.compile \
("[0123]?\d[-/\s\.](?:[01]\d|[a-z]{3,})[-/\s\.](?:\d{2})?\d{2}",re.IGNORECASE)
lib["time"] = re.compile("\d{1,2}:\d{1,2}(?:\s*[aApP]\.?[mM]\.?)?")
lib["fullurl"] = re.compile("https?://[-a-z0-9\.]{4,}(?::\d+)?/[^#?]+(?:#\S+)?",re.IGNORECASE)
lib["visacard"] = re.compile("4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}")
lib["mastercard"] = re.compile("5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}")
lib["phone"] = re.compile("0[-\d\s]{10,}")
lib["ninumber"] = re.compile("[a-z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[a-z]",re.IGNORECASE)
lib["isbn"] = re.compile("(?:[\d]-?){9}[\dxX]")
  '''