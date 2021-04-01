"""
Useful Data Structures for memory cartography analyses
"""

import collections
import pickle
import os
import re

Region = collections.namedtuple("start_addr", "end_addr", "name")

class MapList:
    def __init__(self):
        self.name_counter = {} # tracks number of regions a given name (so they can be renamed appropriately)
        self.regions_dict = {} # dictionary mapping from region name to region start/end 
        self.regions_list = [] # list of mapped regions sorted by start for fast pointer search
        self.list_sorted = True # does the list need to be sorted before searching?
        self.region_compare = lambda x,y : x.start < y.start
    
    def add_region(self, region):
        if region.name not in self.name_counter.keys():
            self.name_counter[region.name] = 1
        else:
            self.name_counter[region.name] += 1
        
        region.name = region.name + "_{}".format(self.name_counter[region.name] - 1)
        if len(self.regions_list) > 0 and region.start < self.regions_list[-1].start:
            self.list_sorted = False

        self.regions_list.append(region)
        self.regions_dict[region.name] = region
        

    def check_pointer(self, addr):
        if not self.list_sorted:
            self.regions_list.sort(self.region_compare)

        lb = 0
        ub = len(self.regions_list)
        while True:
            med = (lb + ub) // 2
            test = self.regions_list[med]
            if test.start <= addr and addr < test.end:
                return test
            elif lb == med:
                return None
            elif test.end <= addr:
                lb = med
            elif addr < test.start:
                ub = med

    # search for region start/end by region name
    def find_region(self, region_name):
        return self.regions_dict[region_name]

class MemoryGraph:
    # sourcelist = subset of nodelist where edges can originate
    def __init__(self, nodelist, srclist=None):
        self.adj_matrix = {} # keys are strings, not region objects
        if srclist is None:
            srclist = nodelist
        for s in srclist:
            self.adj_matrix[s] = {}
            for d in nodelist:
                self.adj_matrix[s][d] = []

    def add_edge(self, src_region, dst_region, src_offset, dst_offset):
        return self.adj_matrix[src_region][dst_offset].append((src_offset, dst_offset))

    def get_outward_edges(self, src):
        return self.adj_matrix[src]

    def get_edges(self, src, dst):
        return self.adj_matrix[src][dst]

# Contains all of the data structures resulting from one run of a target program
# and utilities for analyzing the data
class RunContainer:

    def __init__(self, runname, heapnames=None, path="./", maplist=None, memgraph=None, heap_handles=None):
        self.runname = runname
        self.path = path

        if maplist is None:
            maplist = pickle.load(open(path + runname + "_maplist.pickle", "rb"))

        if memgraph is None:
            memgraph = pickle.load(open(path + runname + "_memgraph.pickle", "rb"))

        if heapnames is None:
            p = re.compile('{}_([.]*_[0-9]).dump'.format(runname))
            heapnames = [p.search(f).group(1) for f in os.listdir(path) if p.match(f)]

        if heap_handles is None:
            heap_handles = [open(path + runname + h + ".dump","rb") for h in heapnames]
    
        self.maplist = maplist
        self.memgraph = memgraph
        self.heap_handles = heap_handles

        self.heap_regions = [maplist.find_region(h) for h in heapnames]

    def read_heap_bytes(self, heapnum, offset, nbytes):
        self.heap_handles[heapnum].seek(offset)
        return self.heap_handles[heapnum].read(nbytes)

    # Look for pointers to (dst_region, offset)
    # Return a nested list containing the offsets of
    # any such pointers for each heap regoin
    def scan_for_pointer(self, dst_region_name, offset):
        addrs = []
        for h in self.heap_regions:
            for edge in self.memgraph.get_edges(h.name, dst_region_name):
                if edge[1] == offset:
                    addrs.append(edge[0])

        return addrs

    # Return a dictionary of the most frequent pointer destinations in this 
    # run. Optionally, add the tally to an existing dictionary.
    def rank_most_frequent(self, pointer_dict=None):
        if pointer_dict is None:
            pointer_dict = {}

        for i,h in enumerate(self.heap_regions):
            for dst in self.memgraph[h.name].keys():
                for ptr in self.memgraph[h.name][dst]:
                    pointer_id = (dst, ptr[1])
                    if pointer_id not in pointer_dict:
                        pointer_dict[pointer_id] = 0
                    pointer_dict[pointer_id][i] += 1

        return pointer_dict

    # Iterate over one of the heaps at a set offset and stride
    def heap_iterator(self, heapnum, offset, stride):
        h = self.heap_handles[heapnum]
        h.seek(offset)
        pos = offset

        mem = h.read(stride)
        while mem:
            yield pos, mem
            pos += stride
            mem = h.read(stride)

    # Convieniance function for getting the length of a heap
    def get_heap_size(self, heapnum):
        return self.heap_regions[heapnum].end - self.heap_regions[heapnum].start


    
