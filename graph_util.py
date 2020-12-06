"""
Graph algorithms for analyzing the memory map
"""
import collections

"""
Find the shortest path using a simple BFS
Graph is a double-dictionary
"""
def shortest_path(graph, start, end):
    if not (start in graph.keys() and end in graph.keys()):
        return None

    visited = set([])
    prev = {}
    for k in graph.keys():
        prev[k] = ""

    nodeq = collections.deque() #FIFO queue
    nodeq.appendleft(start)

    while len(nodeq) > 0:
        currnode = nodeq.pop()
        visited.add(currnode)

        if currnode == end:
            path = []
            step = end
            while len(step) > 0:
                path.insert(0,step)
                step = prev[step]
            return path

        for nxt in graph.keys():
            if len(graph[currnode][nxt]) > 0 and nxt not in visited:
                prev[nxt] = currnode
                nodeq.appendleft(nxt)
    
    return None

"""
Find strongly connected components in the memory graph
graph is a double-dictionary
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

