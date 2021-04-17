"""
Graph algorithms for analyzing the memory map
"""

import data_structures
import argparse

"""
Find strongly connected components in the memory graph
graph is a double-dictionary, like the kind contained 
in the `adj_matrix` field of a data_structures.MemGraph
object. 
"""
def find_scc(graph):
    grev = {} #reverse graph
    for u in graph.keys():
        for v in graph.keys():
            if v not in grev:
                grev[v] = {}
            grev[v][u] = graph[u][v]

    scc_memership = {} # To which number SCC does each node belong?
    sccs = []
    scc_edgelist = []

    visited = set([])
    preo = []
    posto = [] 

    def dfs(g, source):
        visited.add(source)
        preo.append(source)
        for nxt in g.keys():
            if len(g[source][nxt]) > 0 and nxt not in visited:
                visited.add(nxt)
                dfs(g, nxt)
            if len(g[source][nxt]) > 0 and nxt in scc_memership: # for tracing scc edges during 2nd pass
                scc_edgelist[-1].add(scc_memership[nxt]) 
        posto.append(source)

    for src in grev.keys():
        if src not in visited:
            dfs(grev, src)
    
    visited = set([])
    sinks = [x for x in posto[::-1]]
    preo = []
    posto = []

    # get the sccs
    for src in sinks:
        if src not in visited:
            scc_edgelist.append(set([]))
            dfs(graph, src)
            for node in preo:
                scc_memership[node] = len(sccs)
            sccs.append(preo)
            preo = [] #comandeer preo to keep track of new additions

    return sccs, scc_edgelist


"""
Simple DFS that runs on an edgelist and returns the list of nodes reachable from a source
Edgelist is just a list of sets of ints, src is an int
"""
def simple_dfs(edgelist, src):
    visited = set([])
    def search(g, source):
            visited.add(source)
            for nxt in edgelist[source]:
                if  nxt not in visited:
                    visited.add(nxt)
                    search(g, nxt)
    search(edgelist, src)
    return visited

"""
Example Usage: python graph_util.py vim_map/memgraph_final.json --region /usr/bin/vim.basic_4
"""
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", help="graph to be loaded and analyzed")
    parser.add_argument("--region", default=None, help="region of interest")
    args = parser.parse_args()

    mg = data_structures.MemoryGraph(load_file=args.graph)
    scc, edges = find_scc(mg.adj_matrix)
    if args.region is None:
        print(scc)
    else:
        total = sum([len(x) for x in scc])
        roi = [i for i,x in enumerate(scc) if args.region in x][0] # scc constatining region of interest
        rlen = len(scc[roi])
        reachable = simple_dfs(edges, roi)
        n_reachable_reg = sum([len(scc[i]) for i in reachable])

        print("SCC of interest contains {} of {} regions".format(rlen, total))
        print("SCC of interest can reach {} of {} regions".format(n_reachable_reg, total))