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