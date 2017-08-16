# -*- coding: utf-8 -*-

#  git clone https://github.com/radare/radare2.git
from __future__ import print_function
import logging

#import r2pipe

log = logging.getLogger('radare')


# libdl hack
# if self.memory_handler.get_target_platform().get_os_name() not in ['winxp', 'win7']:
#    log.info('[+] Reversing function pointers names')
#    # TODO in reversers
#    # dict(libdl.reverseLocalFonctionPointerNames(self) )
#    self._function_names = dict()




# def get_functions_pointers(self):
#     try:
#         return self.get_cache_radare()
#     except IOError as e:
#         return self.save_cache_radare()
#
# def get_cache_radare(self):
#     dumpname = self.memory_handler.get_name()
#     fname = config.get_cache_filename(config.CACHE_FUNCTION_NAMES, dumpname)
#     functions = None
#     try:
#         with file(fname, 'r') as fin:
#             functions = pickle.load(fin)
#     except EOFError as e:
#         os.remove(fname)
#         log.error('Error in the radare cache file. File cleaned. Please restart.')
#         raise RuntimeError('Error in the radare cache file. File cleaned. Please restart.')
#     return functions
#
# def save_cache_radare(self):
#     from haystack.reverse.heuristics import radare
#     func = radare.RadareAnalysis(self.memory_handler)
#     func.init_all_functions()
#     import code
#     code.interact(local=locals())
#     dumpname = self.memory_handler.get_name()
#     fname = config.get_cache_filename(config.CACHE_FUNCTION_NAMES, dumpname)
#     with file(fname, 'w') as fout:
#         pickle.dump(func.functions, fout)
#     return func.functions

class RadareAnalysis(object):
    """
    Use radare to get more info about non heaps
    """
    def __init__(self, memory_handler):
        self._memory_handler = memory_handler
        self.functions = {}

    def init_all_functions(self):
        for a_map in self._memory_handler.get_mappings():
            self.find_functions(a_map)

    def find_functions(self, mapping):
        fname = mapping._memdumpname
        log.debug('Opening %s', fname)
        # FIXME is that even useful
        import r2pipe
        r2 = r2pipe.open(fname)
        r2.cmd("aaa")
        analysis = r2.cmd("afl")
        print(analysis)
        res = analysis.split('\n')
        log.debug("len %d - %d", len(analysis), len(res))
        #if len(analysis) > 40:
        #    import pdb
        #    pdb.set_trace()
        nb = 0
        for f_line in res:
            if "0x" not in res:
                continue
            addr, size, bbs, name = f_line.split('  ')
            addr = int(addr, 16)
            if addr == 0x0:
                continue
            size = int(size)
            bbs = int(bbs)
            self.functions[mapping.start+addr] = (size, bbs, name)
            nb += 1
        log.debug('Found %d functions in 0x%x', nb, mapping.start)