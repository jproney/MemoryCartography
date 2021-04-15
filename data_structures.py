"""
Useful Data Structures for memory cartography analyses
"""

import collections
import pickle
import os
import re

"""
Named tuple representing a VMA
"""
Region = collections.namedtuple("Region", ["start", "end", "name"])


"""
Class representing the VMAs of a process
"""
class MapList:
    def __init__(self):
        self.name_counter = {} # tracks number of regions a given name (so they can be renamed appropriately)
        self.regions_dict = {} # dictionary mapping from region name to region start/end 
        self.regions_list = [] # list of mapped regions sorted by start for fast pointer search
        self.list_sorted = True # does the list need to be sorted before searching?

    """
    Add a new region to the MapList structure.
    region = region to add. Should be a data_structures.Region object.
    """
    def add_region(self, region):
        if region.name not in self.name_counter.keys():
            self.name_counter[region.name] = 1
        else:
            self.name_counter[region.name] += 1
        
        region = Region(region.start, region.end, region.name + "_{}".format(self.name_counter[region.name] - 1))
        if len(self.regions_list) > 0 and region.start < self.regions_list[-1].start:
            self.list_sorted = False

        self.regions_list.append(region)
        self.regions_dict[region.name] = region
        

    """
    Determines whether a virtual address falls into a region within the
    MapList structure. If it does, return that regions as a data_structures.Region object
    addr = virtual address to check. 
    """
    def check_pointer(self, addr):
        if not self.list_sorted:
            self.regions_list.sort(key = lambda x,y : x.start < y.start)

        # binary search for the right region
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
    """
    search for region start/end by region name
    region_name = string name of desired region. Ex: 'lib.so_4'
    """
    def find_region(self, region_name):
        return self.regions_dict[region_name]

    """
    merge adjascent regions with the same name
    """
    def coalesce(self):
        self.regions_list = []
        newdict = {}
        for name in self.name_counter.keys():
            sublist = []
            for i in range(self.name_counter[name]):
                sublist.append(self.regions_dict[name + "_{}".format(i-1)])
            sublist.sort(key = lambda x,y : x.start < y.start)

            newlist = [Region(start=sublist[0].start, end=sublist[0].end, name=name + "_0")]
            i = 0
            for reg in sublist[1:]:
                if reg.start == newlist[-1].end:
                    newlist[-1] = Region(newlist[-1].start, reg.end, newlist[-1].name)
                else:
                    i += 1
                    newlist.append(Region(reg.start, reg.end, name + "_{}".format(i)))
            
            self.regions_list += newlist
            for reg in newlist:
                newdict[reg.name] = reg

        self.regions_dict = newdict

"""
Class that represents a directed graph of pointers between memory regions
"""
class MemoryGraph:

    """
    nodelist = list of string names of VMAs in the graph
    sourcelist = subset of nodelist where edges can originate.  The remainder of nodes
                 in the graphs can be sinks, but not sources 
    """
    def __init__(self, nodelist, srclist=None):
        self.adj_matrix = {} # keys are strings, not region objects
        if srclist is None:
            srclist = nodelist
        for s in srclist:
            self.adj_matrix[s] = {}
            for d in nodelist:
                self.adj_matrix[s][d] = []

    """
    Add an edge to the graph
    src_region = string name of source for the edge
    dst_regoin = string name of destination for the edge
    src_offset = integer offset of pointer within source region
    dst_offset = integer offset of pointer destination within destination region
    """
    def add_edge(self, src_region, dst_region, src_offset, dst_offset):
        return self.adj_matrix[src_region][dst_region].append((src_offset, dst_offset))

    """
    Get dictionary of edges leaving a particular region
    src = string name of source regoin
    """
    def get_outward_edges(self, src):
        return self.adj_matrix[src]

    """
    Get a list of edges between two regions
    src = string name of source region
    dst = string name of destination region
    returns list of (src_offset, dst_offset) pairs
    """
    def get_edges(self, src, dst):
        return self.adj_matrix[src][dst]

"""
Contains all of the data structures resulting from one run of a target program
and utilities for analyzing the data
"""
class RunContainer:

    """
    runname = prefix for all of the files corresponding to the run. Ex: "run0"
    heapnames = names of the heap regions. Should correspond do files of the form "run0_[region].dump" in the target directory
                If not specified, all files of the form runname + * + '.dump' will be treated as heaps
    path = directory containing the relevant files
    maplist = data_structures.MapList object for the target run. If not provided, will be searched for in the target path
    memgraph = data_structures.MemGraph object for the target run. If not provided, will be searched for in the target path
    heap_handles = list of file handles for the heap dumps. If not provided, will be loaded from files in the target path
    """
    def __init__(self, runname, heapnames=None, path="./", maplist=None, memgraph=None, heap_handles=None):
        self.runname = runname
        self.path = path

        if maplist is None:
            maplist = pickle.load(open(path + runname + "_maplist.pickle", "rb"))

        if memgraph is None:
            memgraph = pickle.load(open(path + runname + "_memgraph.pickle", "rb"))

        if heapnames is None:
            p = re.compile('{}_(.*_[0-9]).dump'.format(runname))
            heapnames = [p.search(f).group(1) for f in os.listdir(path) if p.match(f)]

        if heap_handles is None:
            heap_handles = [open(path + runname + "_" + h + ".dump","rb") for h in heapnames]
    
        self.maplist = maplist
        self.memgraph = memgraph
        self.heap_handles = heap_handles

        self.heap_regions = [maplist.find_region(h) for h in heapnames]

    """
    Read bytes from a particular heap dump within the run
    heapnum = index of the heap to read from
    offset = file offset to read from
    nbytes = number of bytes to read
    """
    def read_heap_bytes(self, heapnum, offset, nbytes):
        self.heap_handles[heapnum].seek(offset)
        return self.heap_handles[heapnum].read(nbytes)

    """
    Scan all heap dumps in this run for pointers to a particular region
    dst_region_name = name of pointer's destination region
    offset = offset within the destination region that the pointer reference
    returns a nested list. Each inner list represents a heap, as contains
    a list of offsets within the heap that contain the target pointer.
    """
    def scan_for_pointer(self, dst_region_name, offset):
        addrs = []
        for h in self.heap_regions:
            heaplist = []
            for edge in self.memgraph.get_edges(h.name, dst_region_name):
                if edge[1] == offset:
                    heaplist.append(edge[0])
            addrs.append(heaplist)

        return addrs

    """
    Return a dictionary of the most frequent pointer destinations in this 
    run. Optionally, add the tally to an existing dictionary.
    pointer_dict = dictionary with keys of the form (destination_name, offset).
                   Values are lists, and each list entry is the number of occurances of 
                   the key pointer in each of the heaps in this run. If not provided,
                   a new dictionary of this format will be generated for the current 
                   run, and can be passed to the `rank_most_frequent` of a different
                   RunContainer object to tally pointer freuquencies accross runs.
    """
    def rank_most_frequent(self, pointer_dict=None):
        if pointer_dict is None:
            pointer_dict = {}

        for h in self.heap_regions:
            for dst in self.memgraph.adj_matrix[h.name].keys():
                for ptr in self.memgraph.adj_matrix[h.name][dst]:
                    pointer_id = (dst, ptr[1])
                    if pointer_id not in pointer_dict:
                        pointer_dict[pointer_id] = 0
                    pointer_dict[pointer_id] += 1

        return pointer_dict

    """
    Iterate over one of the heaps at a set offset and stride
    heapnum = index of the heap to be read from
    stride = how many bytes to shift the read offset by each iteratoin
    preread = number of bytes to read prior to the read offset
    postread = number of bytes ot read after the read offset
    """
    def heap_iterator(self, heapnum, offset, stride, preread, postread):
        h = self.heap_handles[heapnum]
        pos = offset

        h.seek(pos - preread)
        mem = h.read(preread + postread)
        while len(mem) == preread + postread:
            yield pos, [x for x in mem] # yield interval arround pos

            pos += stride
            h.seek(pos - preread)
            mem = h.read(preread + postread)
    """
    Convieniance function for getting the length of a heap
    heapnum = index of the heap in question
    """
    def get_heap_size(self, heapnum):
        return self.heap_regions[heapnum].end - self.heap_regions[heapnum].start