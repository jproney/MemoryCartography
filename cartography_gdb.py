"""
Map out allocated memory regions in a specificed binary.
Example usage:
gdb -x cartography_gdb.py -ex 'py gdb_main(5201, ["[heap]_0"])'
"""

import gdb #won't work unless script is being run under a GDB process
import re
import pickle
import os
import struct
import data_structures
import build_graph

"""
Construct list of contiguous mapped regions, their offsets, and their names
pid = process to attach to and map
numberby = How to number the regions with the same name. If 1, will number the largest regions 0,1,2...
           This is useful for making sure that the same regions have the same name on each run.
           (e.g. heap_0, heap_1, and heap_2 will correspond to the same logical region beween runs)
"""
def build_maplist(pid, coalesce=False):
    gdb.execute("attach " + str(pid))

    maps = [re.split(r'\s{1,}', s)[1:] for s in gdb.execute("info proc mappings", False, True).split("\n")[4:-1]]

    maplist = data_structures.MapList()

    for segment in maps:
        segname = segment[-1]
        if segname == "(deleted)":
            segname = segment[-2] + "_(deleted)"

        region = data_structures.Region(int(segment[0],16), int(segment[1],16), segname)
        maplist.add_region(region)

    if coalesce:
        maplist.coalesce()

    return maplist

"""
Function for dumping memory from regoins of interst. This is helpful in general 
becaues dumping data and then analyzing it from files is much faster than querying
GDB every time we want to look up an address.
maplist = data structure of mapped regions obtained from `build_maptlist`
sources = list of names of regions to dump. If None, will dump every region in maplist
dumpname = prefix to append to the string "[region].dump" where "region" is the region name
length_lb, length_ub = constraints on the length of regions to dump. Useful in scenarios when 
                       we want to dump and analyze all regions of a certain length. This happened
                       when we wanted to find all jemalloc chunks in the firefox heap. 
                      
"""
def dump_mem(maplist, sources=None, dumpname="", length_lb = -1, length_ub = 2**30):
    sourcelist = [reg.name for reg in maplist.regions_list if reg.end - reg.start >= length_lb and reg.end - reg.start <= length_ub]
    if sources:
        sourcelist = [s for s in sourcelist if s in sources]

    for i,src in enumerate(sourcelist):
        print("Dumping " + str(src.name) + " ({}/{})".format(i,len(sourcelist)) + "len = {} bytes".format(src.end - src.start))
        print("dump memory {}.dump {} {}".format(dumpname + src.name.split("/")[-1], src.start, src.end))
        try:
            gdb.execute("dump memory {}.dump {} {}".format(dumpname + src.nmae.split("/")[-1], src.start, src.end))
        except:
            continue
        print("finished dump")


"""
Run the full script and save the memory graph
pid = pid of the process to attach to
sources = names of regions to scan for pointers. If None, all regions will be scanned
online = whether to build the graph online in GDB (slower) or construct the graph from dumps (more space)
name = prefix for all saved files, including pickled data structures and memory dumps
dump = whether to save dumps of osurce regions when scan is done online. Offline scans will automatically
       save dumps
llb, lub = upper and lower bounds on lengths of source regions to scan
numberby = how to number regions with the same name. If 0, order in /proc/maps will be preserved. If 1,
          they will be ordered by decreasing length.
"""
def gdb_main(pid, sources=None, name="", llb = -1, lub=2**30, graph=True, psize=8, coalesce=False):
    maplist = build_maplist(pid, coalesce)
    dump_mem(maplist, sources, name, llb, lub)

    with open(name + "maplist.pickle", "wb") as f:
        pickle.dump(maplist, f)
    if graph:
        memgraph = build_graph.build_graph_from_dumps(maplist, psize, sources, name, llb, lub)
        with open(name + "memgraph.pickle", "wb") as f2:
            pickle.dump(memgraph, f2)

    gdb.execute("detach")
    gdb.execute("quit")