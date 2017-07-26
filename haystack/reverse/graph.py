#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Loic Jaquemet loic.jaquemet+python@gmail.com
#

from __future__ import print_function

from collections import defaultdict

import networkx
import argparse
import logging
import os
import sys

import matplotlib.pyplot as plt
from haystack import argparse_utils
from haystack.mappings import folder
from haystack.reverse import config
from haystack.reverse import utils
from haystack import cli
from networkx.drawing.nx_agraph import graphviz_layout

"""
Graph tools to represent allocations in a graph.
That allows graph algorithms applications.
"""


log = logging.getLogger('graph')


def print_graph(G, memory_handler):
    h = networkx.DiGraph()
    h.add_edges_from(G.edges())
    # networkx.draw_graphviz(h)
    layout = graphviz_layout(h)
    networkx.draw(h, layout)
    filename = memory_handler.get_name()
    print(filename)
    bname = os.path.basename(filename)
    cache_dir = config.get_cache_folder_name(filename)
    print(cache_dir)
    fname = os.path.sep.join([cache_dir, 'graph_%s.png' % bname])
    plt.savefig(fname)
    plt.clf()
    fname = os.path.sep.join([cache_dir, 'graph_%s.gexf' % bname])
    networkx.readwrite.gexf.write_gexf(h, fname)
    return

# extract graph


def depthSubgraph(source, target, nodes, depth):
    if depth == 0:
        return
    depth -= 1
    for node in nodes:
        neighbors = source.successors(node)
        target.add_edges_from(source.edges(node))
        depthSubgraph(source, target, neighbors, depth)
    return


def save_graph_headers(ctx, graph, fname):
    fout = open(os.path.sep.join([config.cacheDir, fname]), 'w')
    towrite = []
    structs = [ctx.structures[int(addr, 16)] for addr in graph.nodes()]
    for anon in structs:
        print(anon)
        towrite.append(anon.to_string())
        if len(towrite) >= 10000:
            try:
                fout.write('\n'.join(towrite))
            except UnicodeDecodeError as e:
                print('ERROR on ', anon)
            towrite = []
            fout.flush()
    fout.write('\n'.join(towrite))
    fout.close()
    return


def make(opts):
    memory_handler = cli.make_memory_handler(opts)

    #digraph=networkx.readwrite.gexf.read_gexf(  '../../outputs/skype.1.a.gexf')
    digraph = networkx.readwrite.gexf.read_gexf(opts.gexf.name)
    finder = memory_handler.get_heap_finder()
    heap = finder.list_heap_walkers()[0]

    # only add heap structure with links
    # edges = [
    #     (x, y) for x, y in digraph.edges() if int(
    #         x, 16) in heap and int(
    #         y, 16) in heap]
    heap_mapping = heap.get_heap_mapping()
    edges = [(x, y) for x, y in digraph.edges() if int(x, 16) in heap_mapping and int(y, 16) in heap_mapping]
    graph = networkx.DiGraph()
    graph.add_edges_from(edges)

    print_graph(graph, memory_handler)


def clean(digraph):
    # clean solos
    isolates = networkx.algorithms.isolate.isolates(digraph)
    digraph.remove_nodes_from(isolates)

    # clean solos clusters
    graph = networkx.Graph(digraph)  # undirected
    subgraphs = networkx.algorithms.components.connected.connected_component_subgraphs(
        graph)
    isolates1 = set(utils.flatten(g.nodes() for g in subgraphs if len(g) == 1))  # self connected
    isolates2 = set(utils.flatten(g.nodes() for g in subgraphs if len(g) == 2))
    isolates3 = set(utils.flatten(g.nodes() for g in subgraphs if len(g) == 3))
    digraph.remove_nodes_from(isolates1)
    digraph.remove_nodes_from(isolates2)
    digraph.remove_nodes_from(isolates3)

    #
    #graph = digraph.to_undirected()
    #subgraphs = networkx.algorithms.components.connected.connected_component_subgraphs(graph)
    subgraphs = [g for g in subgraphs if len(g) > 3]
    isolatedGraphs = subgraphs[1:100]

    # group by nodes number
    isoDict = defaultdict(list)
    [isoDict[len(g)].append(g) for g in isolatedGraphs]

    # test isomorphism
    isoGraphs = dict()
    for numNodes, graphs in isoDict.items():
        numgraphs = len(graphs)
        if numgraphs == 1:
            continue
        isoGraph = networkx.Graph()
        # quick find isomorphisms
        todo = set(graphs)
        for i, g1 in enumerate(graphs):
            for g2 in graphs[i + 1:]:
                if networkx.is_isomorphic(g1, g2):
                    print('numNodes:%d graphs %d, %d are isomorphic' % (numNodes, i, i + 1))
                    isoGraph.add_edge(g1, g2, {'isomorphic': True})
                    if g2 in todo:
                        todo.remove(g2)
                    if g1 in todo:
                        todo.remove(g1)
                    # we can stop here, chain comparaison will work between g2
                    # and g3
                    break

        if len(isoGraph) > 0:
            isoGraphs[numNodes] = isoGraph

    # draw the isomorphisms
    for i, item in enumerate(isoGraphs.items()):
        num, g = item
        # networkx.draw(g)
        for rg in g.nodes():
            networkx.draw(rg)
        fname = os.path.sep.join(
            [config.imgCacheDir, 'isomorph_subgraphs_%d.png' % num])
        plt.savefig(fname)
        plt.clf()
    # need to use gephi-like for rendering nicely on the same pic

    bigGraph = networkx.DiGraph()
    bigGraph.add_edges_from(digraph.edges(subgraphs[0].nodes()))

    stack_addrs = utils.int_array_cache(
        config.get_cache_filename(config.CACHE_STACK_VALUES, ctx.dumpname, ctx._heap_addr))
    stack_addrs_txt = set(['%x' % addr
                           for addr in stack_addrs])  # new, no long

    stacknodes = list(set(bigGraph.nodes()) & stack_addrs_txt)
    print('stacknodes left', len(stacknodes))
    orig = list(set(graph.nodes()) & stack_addrs_txt)
    print('stacknodes orig', len(orig))

    # identify strongly referenced allocators
    degreesList = [(bigGraph.in_degree(node), node)
                   for node in bigGraph.nodes()]
    degreesList.sort(reverse=True)

# important struct


def printImportant(ctx, digraph, degreesList, ind, bigGraph):
    nb, saddr = degreesList[ind]
    addr = int(saddr, 16)
    s1 = ctx.structures[addr]  # TODO FIXME RAISES
    # s1 = s1._load() #structure.cacheLoad(ctx, int(saddr,16))
    s1.decodeFields()
    print(s1.to_string())
    # strip the node from its predecessors, they are numerously too numerous
    impDiGraph = networkx.DiGraph()
    root = '%d nodes' % nb
    impDiGraph.add_edge(root, saddr)
    depthSubgraph(bigGraph, impDiGraph, [saddr], 2)
    print('important struct with %d structs pointing to it, %d pointerFields' % (
    digraph.in_degree(saddr), digraph.out_degree(saddr)))
    # print 'important struct with %d structs pointing to it, %d
    # pointerFields'%(impDiGraph.in_degree(saddr),
    # impDiGraph.out_degree(saddr))
    fname = os.path.sep.join(
        [config.imgCacheDir, 'important_%s.png' % saddr])
    networkx.draw(impDiGraph)
    plt.savefig(fname)
    plt.clf()
    # check for children with identical sig
    for node in impDiGraph.successors(saddr):
        st = ctx.structures[int(node, 16)]
        st.decodeFields()
        # FIXME rework, usage of obselete function
        st.resolvePointers()
        # st.pointerResolved=True
        # st._aggregateFields()
        print(node, st.get_signature(text=True))
    # clean and print
    # s1._aggregateFields()
    impDiGraph.remove_node(root)
    save_graph_headers(ctx, impDiGraph, '%s.subdigraph.py' % saddr)
    return s1


def deref(ctx, f):
    ctx.structures[f.target_struct_addr].decodeFields()
    return ctx.structures[f.target_struct_addr]

# s1 = printImportant(0) # la structure la plus utilisee.

# TODO
#
# get nodes with high out_degree,
# compare their successors signature, and try to find a common sig sig1
# if sig1 , lone, sig1 , .... , try to fit lone in sig1 ( zeroes/pointers)
# aggregate group of successors given the common sig

# identify chained list ( see isolatedGraphs[0] )

# b800dcc is a big kernel

# print deref(sb800[7]).toString()
#>>> hex(16842753)
#'0x1010001'  -> bitfield


# s1._aggregateFields()

#s2 = utils.nextStructure(ctx, s1)
# s2b should start with \x00's


def main(argv):
    argv = sys.argv[1:]
    desc = 'Play with graph repr of pointers relationships.'
    rootparser = cli.base_argparser(program_name=os.path.basename(sys.argv[0]), description=desc)
    rootparser.add_argument('gexf', type=argparse.FileType('rb'), action='store', help='Source gexf.')
    rootparser.set_defaults(func=make)
    opts = rootparser.parse_args(argv)
    # apply verbosity
    cli.set_logging_level(opts)
    # execute function
    opts.func(opts)
    return

if __name__ == '__main__':
    main(sys.argv[1:])
