import collections
import logging
import os
import time

import matplotlib.pyplot as plt
import networkx
from networkx.drawing.nx_agraph import graphviz_layout

from haystack.reverse import config
from haystack.reverse import context
from haystack.reverse import utils
from haystack.reverse.heuristics import model
from haystack.reverse.heuristics.reversers import log

log = logging.getLogger("graph")

class PointerGraphReverser(model.AbstractReverser):
    """
      Use the pointer relation between structure to map a graph.
    """
    REVERSE_LEVEL = 150

    def __init__(self, _memory_handler):
        super(PointerGraphReverser, self).__init__(_memory_handler)
        # process graph
        self._master_graph = networkx.DiGraph()
        # process graph with only valid heap records
        self._heaps_graph = networkx.DiGraph()
        # heap context graph
        self._graph = None

    def reverse(self):
        super(PointerGraphReverser, self).reverse()
        dumpname = self._memory_handler.get_name()
        outname1 = os.path.sep.join([config.get_cache_folder_name(dumpname), config.CACHE_GRAPH])
        outname2 = os.path.sep.join([config.get_cache_folder_name(dumpname), config.CACHE_GRAPH_HEAP])

        log.info('[+] Process Graph == %d Nodes', self._master_graph.number_of_nodes())
        log.info('[+] Process Graph == %d Edges', self._master_graph.number_of_edges())
        networkx.readwrite.gexf.write_gexf(self._master_graph, outname1)
        log.info('[+] Process Heaps Graph == %d Nodes', self._heaps_graph.number_of_nodes())
        log.info('[+] Process Heaps Graph == %d Edges', self._heaps_graph.number_of_edges())
        networkx.readwrite.gexf.write_gexf(self._heaps_graph, outname2)
        return

    def reverse_context(self, _context):
        # we only need the addresses...
        self._graph = networkx.DiGraph()
        t0 = time.time()
        tl = t0
        context_heap = hex(_context._heap_start)
        for _record in _context.listStructures():
            # in all case
            self._graph.add_node(hex(_record.address), heap=context_heap, weight=len(_record))
            self._master_graph.add_node(hex(_record.address), heap=context_heap, weight=len(_record))
            self._heaps_graph.add_node(hex(_record.address), heap=context_heap, weight=len(_record))
            self.reverse_record(_context, _record)
            # output headers
        #
        log.info('[+] Heap %s Graph += %d Nodes', context_heap, self._graph.number_of_nodes())
        log.info('[+] Heap %s Graph += %d Edges', context_heap, self._graph.number_of_edges())
        # save the whole graph
        networkx.readwrite.gexf.write_gexf(self._graph, _context.get_filename_cache_graph())
        # save the graph pruned of less connected nodes
        self.clean_graph(_context, self._graph)
        networkx.readwrite.gexf.write_gexf(self._graph, _context.get_filename_cache_graph_connected())
        # save a PNG of that
        self.print_graph(self._graph, _context.get_filename_cache_graph_png())
        return

    def reverse_record(self, heap_context, _record):
        ptr_value = _record.address
        # targets = set(( '%x'%ptr_value, '%x'%child.target_struct_addr )
        # for child in struct.getPointerFields()) #target_struct_addr
        # target_struct_addr

        pointer_fields = [f for f in _record.get_fields() if f.type.is_pointer()]
        for f in pointer_fields:
            pointee_addr = f.value
            # we always feed these two
            # TODO: if a Node is out of heap/segment, replace it by a virtual node & color representing
            # the foreign heap/segment
            self._graph.add_edge(hex(_record.address), hex(pointee_addr))
            # add a colored node
            self._master_graph.add_edge(hex(_record.address), hex(pointee_addr))
            # but we only feed the heaps graph if the target is known
            heap = self._memory_handler.get_mapping_for_address(pointee_addr)
            try:
                heap_context = context.get_context_for_address(self._memory_handler, pointee_addr)
            except ValueError as e:
                continue
            #heap_context = self._memory_handler.get_reverse_context().get_context_for_heap(heap)
            if heap_context is None:
                continue
            # add a heap color
            context_heap = hex(heap_context._heap_start)
            self._graph.add_node(hex(pointee_addr), heap=context_heap)
            self._master_graph.add_node(hex(pointee_addr), heap=context_heap)
            self._heaps_graph.add_node(hex(pointee_addr), heap=context_heap)
            try:
                pointee = heap_context.get_record_at_address(pointee_addr)
            except IndexError as e:
                continue
            except ValueError as e:
                continue
            self._heaps_graph.add_edge(hex(_record.address), hex(pointee_addr))
            # add a weight
            self._graph.add_node(hex(pointee_addr), weight=len(_record))
            self._master_graph.add_node(hex(pointee_addr), weight=len(_record))
            self._heaps_graph.add_node(hex(pointee_addr), weight=len(_record))
        return

    def load_process_graph(self):
        dumpname = self._memory_handler.get_name()
        fname = os.path.sep.join([config.get_cache_folder_name(dumpname), config.CACHE_GRAPH])
        my_graph = networkx.readwrite.gexf.read_gexf(fname)
        return my_graph

    def print_graph(self, _graph, filename):
        # h = networkx.DiGraph()
        # # keep only connected things
        # h.add_edges_from(_graph.edges())
        # # networkx.draw_graphviz(h)
        layout = graphviz_layout(_graph)
        networkx.draw(_graph, layout)
        # save the png
        plt.savefig(filename)
        plt.clf()
        return

    def clean_graph(self, _context, digraph):
        """
        clean digraph to remove isolates and cluster with less than 4 nodes
        then group clusters by isomorphism


        :param _context:
        :param digraph:
        :return:
        """
        # clean solos
        isolates = networkx.algorithms.isolate.isolates(digraph)
        digraph.remove_nodes_from(isolates)

        # clean solos clusters
        graph = networkx.Graph(digraph)  # undirected
        subgraphs = networkx.algorithms.components.connected.connected_component_subgraphs(graph)
        # remove records linked to less than 3 records
        isolates2 = set(utils.flatten(g.nodes() for g in subgraphs if len(g) in [1, 2, 3]))
        # remove isolates from digraph
        digraph.remove_nodes_from(isolates2)

        # basically diagraph in a non oriented Graph
        subgraphs = [g for g in subgraphs if len(g) > 3]
        isolated_graphs = subgraphs[1:100]

        # group by nodes number
        isoDict = collections.defaultdict(list)
        for g in isolated_graphs:
            isoDict[len(g)].append(g)

        # test isomorphism
        iso_graphs = dict()
        for numNodes, graphs in isoDict.items():
            numgraphs = len(graphs)
            if numgraphs == 1:
                continue
            iso_graph = networkx.Graph()
            # quick find isomorphisms
            todo = set(graphs)
            for i, g1 in enumerate(graphs):
                for g2 in graphs[i + 1:]:
                    if networkx.is_isomorphic(g1, g2):
                        log.debug('numNodes:%d graphs %d, %d are isomorphic', numNodes, i, i + 1)
                        iso_graph.add_edge(g1, g2, {'isomorphic': True})
                        if g2 in todo:
                            todo.remove(g2)
                        if g1 in todo:
                            todo.remove(g1)
                        # we can stop here, chain comparaison will work between g2
                        # and g3
                        break

            if len(iso_graph) > 0:
                iso_graphs[numNodes] = iso_graph

        # draw the isomorphisms
        for i, item in enumerate(iso_graphs.items()):
            num, g = item
            # networkx.draw(g)
            for rg in g.nodes():
                networkx.draw(rg)
            self.print_graph(g, _context.get_filename_cache_graph_isomorphic(num))

        #

    def locate_important(self, ctx, digraph, subgraphs):
            # FIXMe: identify purpose.
            # seems to locate the most connected record.

            # need to use gephi-like for rendering nicely on the same pic
            big_graph = networkx.DiGraph()
            big_graph.add_edges_from(digraph.edges(subgraphs[0].nodes()))

            # identify strongly referenced allocators
            degrees_list = [(big_graph.in_degree(node), node) for node in big_graph.nodes()]
            degrees_list.sort(reverse=True)

            nb, saddr = degrees_list[0]
            addr = int(saddr, 16)
            s1 = ctx.get_record_for_address(addr)
            log.debug(s1.to_string())
            # strip the node from its predecessors, they are numerously too numerous
            impDiGraph = networkx.DiGraph()
            root = '%d nodes' % nb
            impDiGraph.add_edge(root, saddr)
            depthSubgraph(bigGraph, impDiGraph, [saddr], 2)
            log.debug('important struct with %d structs pointing to it, %d pointerFields' % (
                digraph.in_degree(saddr), digraph.out_degree(saddr)))
            # print 'important struct with %d structs pointing to it, %d
            # check for children with identical sig
            for node in impDiGraph.successors(saddr):
                st = ctx.structures[int(node, 16)]
                st.decodeFields()
                # FIXME rework, usage of obsolete function
                st.resolvePointers()
                # st.pointerResolved=True
                # st._aggregateFields()
                print(node, st.get_signature(text=True))
            # clean and print
            # s1._aggregateFields()
            impDiGraph.remove_node(root)
            self.print_graph(impDiGraph, ctx.get_filename_cache_graph_important(saddr))
            return s1


def depthSubgraph(source, target, nodes, depth):
    if depth == 0:
        return
    depth -= 1
    for node in nodes:
        neighbors = source.successors(node)
        target.add_edges_from(source.edges(node))
        depthSubgraph(source, target, neighbors, depth)
    return
