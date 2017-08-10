# -*- coding: utf-8 -*-

import collections
import logging
from collections import Counter

from haystack.reverse.heuristics import model

log = logging.getLogger('constraints')


class FieldValueRangeReverser(model.AbstractReverser):
    """
        List all records type
        And create the value range of each field for each record type
        Save that to file

        # TODO implement a count verificator to ensure that all process printed types account
        to the sum of all heap records types

    """

    REVERSE_LEVEL = 350

    def __init__(self, memory_handler, output_to_file=True):
        super(FieldValueRangeReverser, self).__init__(memory_handler)
        self.all_records_types = collections.defaultdict(list)
        self.all_records_types_field_value_ranges = collections.defaultdict(dict)
        self._output_to_file = output_to_file

    def reverse(self):
        if self._output_to_file:
            with open(self._memory_handler.get_reverse_context().get_filename_cache_headers(), 'w') as fout:
                towrite = ['# This file contains record types deduplicated by instance',
                           '# Unique values for each field of the record are listed']
                fout.write('\n'.join(towrite))
                fout.flush()
        super(FieldValueRangeReverser, self).reverse()

    def reverse_context(self, _context):
        if self._output_to_file:
            with open(_context.get_filename_cache_headers(), 'w') as fout:
                towrite = ['# This file contains record types deduplicated by instance',
                           '# Unique values for each field of the record are listed']
                fout.write('\n'.join(towrite))
                fout.flush()
        #
        nb_total = 0
        ctx_record_types = collections.defaultdict(list)
        ctx_value_ranges = collections.defaultdict(dict)
        record_types = set()
        for record in _context.listStructures():
            self.all_records_types[record.record_type.type_name].append(record.address)
            ctx_record_types[record.record_type.type_name].append(record.address)
            record_types.add(record.record_type)
            nb_total += 1
        #

        for record_type in record_types:
            # nb_total += len(members_addresses)
            value_range = self.reverse_record_type(_context, record_type, ctx_record_types)
            # FIXME update of dict with conflicting keys...
            self.all_records_types_field_value_ranges[record_type.type_name].update(value_range)
            ctx_value_ranges[record_type.type_name] = value_range

        nb_unique = len(record_types)
        # ordered print out to file
        if self._output_to_file:
            record_types_ordered = list(record_types)
            record_types_ordered.sort(key=lambda x: x.size)
            for record_type in record_types_ordered:
                self.output_to_file(_context, record_type, ctx_record_types, ctx_value_ranges)
        # add some stats
        log.info('# Stats: unique_types:%d total_instances:%d' % (nb_unique, nb_total))
        return

    def reverse_record_type(self, _context, _record_type, ctx_record_types):
        # we want the addresses of the instances
        members_addresses = ctx_record_types[_record_type.type_name]
        value_range = collections.defaultdict(list)

        # gather fields values
        for record_addr in members_addresses:
            record = _context.get_record_for_address(record_addr)
            for field in record.get_fields():
                if field.type.is_record():
                    continue
                if field.type.is_pointer():
                    val = hex(field.value)
                elif field.type.is_zeroes():
                    val = 0
                else:
                    val = field.value
                value_range[field.type.name].append(val)
        # replace values with Counter
        for name, values in value_range.items():
            counter = Counter(values)
            value_range[name] = counter
        return value_range

    def output_to_file(self, _context, _record_type, ctx_record_types, ctx_value_ranges):
        """
        Save the python class code definition to file.
        """
        # heap context
        header_lines = []
        members_addresses = ctx_record_types[_record_type.type_name]
        header_lines.append('# size: %d' % _record_type.size)
        header_lines.append('# signature: %s' % _record_type.signature_text)
        header_lines.append("# %d instances" % len(members_addresses))
        header_lines.append('# @ instances: [%s]' % (','.join(['0x%x' % addr for addr in members_addresses])))
        # output fields values
        for field_decl_name, counter in ctx_value_ranges[_record_type.type_name].items():
            header_lines.append('# field: %s values: %s' % (field_decl_name, counter))
        with open(_context.get_filename_cache_headers(), 'a') as fout:
            fout.write('\n'.join(header_lines))
            fout.write(_record_type.to_string())
            fout.flush()

        # process_context
        header_lines = []
        members_addresses = self.all_records_types[_record_type.type_name]
        header_lines.append('# size: %d' % _record_type.size)
        header_lines.append('# signature: %s' % _record_type.signature_text)
        header_lines.append("# %d instances" % len(members_addresses))
        header_lines.append('# @ instances: [%s]' % (','.join(['0x%x' % addr for addr in members_addresses])))
        # output fields values
        for field_decl_name, counter in ctx_value_ranges[_record_type.type_name].items():
            header_lines.append('# field: %s values: %s' % (field_decl_name, counter))
        with open(self._memory_handler.get_reverse_context().get_filename_cache_headers(), 'a') as fout:
            fout.write('\n'.join(header_lines))
            fout.write(_record_type.to_string())
            fout.flush()
        return
