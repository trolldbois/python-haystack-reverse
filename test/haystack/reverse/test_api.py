from __future__ import print_function

import logging
import unittest

from haystack.mappings import folder

from haystack.reverse import api

log = logging.getLogger("test_reverse_api")


class TestReverseApi(unittest.TestCase):

    def setUp(self):
        dumpname = 'test/src/test-ctypes6.64.dump'
        # config.remove_cache_folder(dumpname)
        self.memory_handler = folder.load(dumpname)
        process_context = self.memory_handler.get_reverse_context()

    def tearDown(self):
        self.memory_handler.reset_mappings()
        self.memory_handler = None

    def test_a_reverse_instances(self):
        api.reverse_instances(self.memory_handler)
        # TODO
        return

    def test_pred(self):
        addr = 0x1d96cd0
        process_context = self.memory_handler.get_reverse_context()
        heap_context = process_context.get_context_for_address(addr)
        # ordered allocation
        allocs = heap_context.list_allocations_addresses()
        # self.assertEqual(allocs[0], addr)
        _record = api.get_record_at_address(self.memory_handler, addr)
        self.assertEqual(_record.address, addr)
        #self.assertEqual(len(_record.get_fields()), 3)
        print(_record.to_string())
        # FIXME - process must be reversed. Graph must be generated.
        pred = api.get_record_predecessors(self.memory_handler, _record)
        print('pred', pred)
        for p in pred:
            print(p.to_string())
        pass



if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # logging.getLogger("listmodel").setLevel(logging.DEBUG)
    # logging.getLogger("reversers").setLevel(logging.DEBUG)
    # logging.getLogger("signature").setLevel(logging.DEBUG)
    # logging.getLogger("test_reversers").setLevel(logging.DEBUG)
    # logging.getLogger("structure").setLevel(logging.DEBUG)
    # logging.getLogger("dsa").setLevel(logging.DEBUG)
    # logging.getLogger("winxpheap").setLevel(logging.DEBUG)
    unittest.main(verbosity=2)
