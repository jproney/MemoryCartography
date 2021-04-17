"""
Map out allocated memory regions in a specificed binary.
Not a standalone python file -- needs to run under GDB.
Called by harvest_heap_data.py
"""

import gdb #won't work unless script is being run under a GDB process
import re
import os
import struct
import sys

# GDB's python interpreter needs this to locate the other files
sys.path.append(os.path.dirname(__file__))

import data_structures
import build_graph

"""
Construct list of contiguous mapped region names, their starting virtual addresses, their end  virtual adresses
In many cases there are multiple VMAs with the same name. To deal with this, we append indices to the region names.
For example, if there are three regions called libc.so, they will become libc.so_0, libc.s0_1, libc.so_2
pid = process to attach to and map
coalesce = whether or not to merge adjascent VMAs that have the same name
"""
def build_maplist(pid, coalesce=False):
    gdb.execute("attach " + str(pid))

    # parse the VMA table printed by gdb
    maps = [re.split(r'\s{1,}', s)[1:] for s in gdb.execute("info proc mappings", False, True).split("\n")[4:-1]]

    maplist = data_structures.MapList()

    for segment in maps:
        segname = segment[-1]
        if segname == "(deleted)":
            segname = segment[-2] + "_(deleted)"

        region = data_structures.Region(int(segment[0],16), int(segment[1],16), segname) # (start, end, name)
        maplist.add_region(region)

    if coalesce:
        maplist.coalesce()

    return maplist

"""
Function for dumping memory from regoins of interst. This is helpful in general 
becaues dumping data and then analyzing it from files is much faster than querying
GDB every time we want to look up an address.
maplist = data structure of mapped regions obtained from `build_maptlist`
sources = list of names of regions to dump. If None, will dump every region in maplist. Note that
          the names of the sources in `sourcelist` do not include the index (i.e., they are of the 
          form 'libc.so' instead of 'libc.so_4')
dumpname = prefix to append to the string "[region].dump" where "[region]" is the region name
length_lb, length_ub = constraints on the length of regions to dump. Useful in scenarios when 
                       we want to dump and analyze all regions of a certain length. This happened
                       when we wanted to find all jemalloc chunks in the firefox heap. 
                      
"""
def dump_mem(maplist, sources=None, dumpname="", length_lb = -1, length_ub = 2**30):
    sourcelist = [reg for reg in maplist.regions_list if reg.end - reg.start >= length_lb and reg.end - reg.start <= length_ub]
    if sources:
        sourcelist = [s for s in sourcelist if "_".join(s.name.split("_")[:-1]) in sources]

    for i,src in enumerate(sourcelist):
        print("Dumping " + str(src.name) + " ({}/{})".format(i,len(sourcelist)) + "len = {} bytes".format(src.end - src.start))
        try:
            # will save dump in file dumpname + region_name, where region_name is the section of the VMA name
            # after the last '/' character. Prevents path issues with the saved file.
            gdb.execute("dump memory {}.dump {} {}".format(dumpname + src.name.split("/")[-1], src.start, src.end))
        except:
            continue
        print("finished dump")


"""
Run the full script and save the memory graph
pid = pid of the process to attach to
sources = names of regions to scan for pointers. If None, all regions will be scanned
name = prefix for all saved files, including serialized data structures and memory dumps
llb, lub = upper and lower bounds on lengths of source regions to scan
coalesce = whether to aggregate adjascent regions with the same name
"""
def gdb_main(pid, sources=None, name="", llb = -1, lub=2**30, graph=True, psize=8, coalesce=False):
    maplist = build_maplist(pid, coalesce)
    dump_mem(maplist, sources, name, llb, lub)

    maplist.serialize(name + "maplist.json")
    if graph:
        memgraph = build_graph.build_graph_from_dumps(maplist, psize, sources, name, llb, lub)
        memgraph.serialize(name + "memgraph.json")

    gdb.execute("detach")
    gdb.execute("quit")