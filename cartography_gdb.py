"""
Map out allocated memory regions in a specificed binary.
Example usage:
gdb -x cartography_gdb.py -ex 'py gdb_main(5201, ["[heap]_0"])'
"""

import gdb #won't work unless script is being run under a GDB process
import re
import pickle
import os

"""
Construct list of contiguous mapped regions, their offsets, and their names
pid = process to attach to and map
numberby = How to number the regions with the same name. If 1, will number the largest regions 0,1,2...
           This is useful for making sure that the same regions have the same name on each run.
           (e.g. heap_0, heap_1, and heap_2 will correspond to the same logical region beween runs)
"""
def build_maplist(pid, numberby=0):
    gdb.execute("attach " + str(pid))

    maps = [re.split(r'\s{1,}', s)[1:] for s in gdb.execute("info proc mappings", False, True).split("\n")[4:-1]]
    # Dict of address data. Keys are segment names. Each dict entry is a list of tuples containing all of the mapped ranges with that name
    mapdict={} 
    for segment in maps:
        segname = segment[-1]
        if segname == "(deleted)":
            segname = segment[-2] + "_(deleted)"
        if segname not in mapdict:
            mapdict[segname] = [(int(segment[0],16), int(segment[1],16))] # create a new key if this is the first instance of this name
        else:
            mapdict[segname].append((int(segment[0],16), int(segment[1],16))) # just extend the list of ranges
        
    # flat version of mapped memory reigons. List of tuples of form (start, end, name), where "name" includes an
    # index to keep ranges from having the same name 
    maplist=[] 
    for seg in mapdict.keys():
        rangelist = mapdict[seg]

        if numberby == 1:
            # Number by size, descending.
            rangelist.sort(key=lambda reg: reg[1] - reg[0], reverse=True)

        for i,reg in enumerate(rangelist):
            maplist.append((reg[0], reg[1], seg + "_" + str(i))) #numeric index makes names unique

    print(maplist)
    return sorted(maplist, key = lambda x: x[0]) # Sort all of the allocated regions by start. Allows for binary search.


"""
Check whether address is mapped
addr = address to check
maplist = data structure containing mapped regions. Obtained from above function
returns (offset, name) where name identifies the region in maplist, and offet is the 
offset of the address within that region. 
If the address is not mapped, return None
"""
def check_pointer(addr, maplist):
     #is val a pointer to any of our mapped regions? Binary search for correct region
     lb = 0
     ub = len(maplist)
     while True:
        med = (lb + ub) // 2
        test = maplist[med]
        if test[0] <= addr and addr < test[1]:
            return addr - test[0], test[2]
        elif lb == med:
            return None
        elif test[1] <= addr:
            lb = med
        elif addr < test[0]:
            ub = med

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
    sourcelist = [x for x in maplist if x[2].split("_")[0] in sources] if sources else maplist
    sourcelist = [x for x in sourcelist if length_lb <= x[1] - x[0] and length_ub >= x[1] - x[0]]

    for i,region in enumerate(sourcelist):
        print("Dumping " + str(region) + " ({}/{})".format(i,len(sourcelist)) + "len = {} bytes".format(region[1] - region[0]))
        print("dump memory {}.dump {} {}".format(dumpname + region[2].split("/")[-1], region[0], region[1]))
        try:
            gdb.execute("dump memory {}.dump {} {}".format(dumpname + region[2].split("/")[-1], region[0], region[1]))
        except:
            continue
        print("finished dump")

"""
Build the Memory Cartography graph while the program is still running in GDB
maplist = data structure containing mapped regions, obtained from `build_maplist`
sources = list of regions to scan for outgoing pointers. If None, scan everything
dump = whether to dump the source regoins (useful for offline learning analyses)
dumpame = prefix for dump files
length_lb, length_ub = length filters on the list of sources to scan. 
                        as in `dump_mem`, this can be useful if many sources have the
                        same name and only some are relevant
"""
def build_graph(maplist, sources=None, dump=False, dumpname="", length_lb = -1, length_ub = 2**30): # sources = list of source ranges to scan, if None, scan everything, fulldump = dump all of the source regions
    memgraph = {} # adjacency matrix, where entry [i][j] is a list of (src_offset, dst_offset) links between regions i and j
    sourcelist = [x for x in maplist if x[2].split("_")[0] in sources] if sources else maplist
    sourcelist = [x for x in sourcelist if length_lb <= x[1] - x[0] and length_ub >= x[1] - x[0]]

    for  _, _, name_i in sourcelist:
        memgraph[name_i] = {}
        for _,_, name_j in maplist:
            memgraph[name_i][name_j] = [] 

    print(sourcelist)

    for i,region in enumerate(sourcelist):
        print("Scanning " + str(region) + " ({}/{})".format(i,len(sourcelist)) + "len = {} bytes".format(region[1] - region[0]))
        if dump:
            gdb.execute("dump memory {}.dump {} {}".format(dumpname + region[2], region[0], region[1]))
        for addr in range(region[0], region[1], 8):
            if (addr - region[0]) % ((region[1] - region[0])//10) == 0:
                print("{}%".format(10*(addr - region[0]) / ((region[1] - region[0])//10)))
            try:
                val = int(gdb.execute("x/g " + str(addr), False, True).split()[-1])
            except:
                continue
            dst = check_pointer(val, maplist)
            if dst:
                # print(dst)
                offset, dstseg = dst
                memgraph[region[2]][dstseg].append((addr - region[0], offset))
    return memgraph


"""
Build the Memory Cartography graph offline from dump files
maplist = data structure containing mapped regions, obtained from `build_maplist`
sources = list of regions to scan for outgoing pointers. If None, scan everything.
          All the sources have to have a corresponding dump file on the disk.
dumpame = prefix for dump files (for loading them, not for saving them)
length_lb, length_ub = length filters on the list of sources to scan. 
"""
def build_graph_from_dumps(maplist, sources=None, dumpname="", length_lb = -1, length_ub = 2**30):
    memgraph = {} #adjacency matrix, where entry [i][j] is a list of (src_offset, dst_offset) links between regions i and j
    sourcelist = [x for x in maplist if x[2].split("_")[0] in sources] if sources else maplist
    sourcelist = [x for x in sourcelist if length_lb <= x[1] - x[0] and length_ub >= x[1] - x[0]]
    
    for  _, _, name_i in sourcelist:
        memgraph[name_i] = {}
        for _,_, name_j in maplist:
            memgraph[name_i][name_j] = [] 

    for i,region in enumerate(sourcelist):
        # Same deal as using gdb, just read from dumps instead
        print("Scanning " + str(region) + " ({}/{})".format(i,len(sourcelist)) + "len = {} bytes".format(region[1] - region[0]))

        if os.path.exists("{}.dump".format(dumpname + region[2].split("/")[-1])):
            with open("{}.dump".format(dumpname + region[2].split("/")[-1]), "rb") as f:
                addr = region[0]
                raw_mem = f.read(8)

                while raw_mem:
                    val = int.from_bytes(raw_mem, "little")
                    dst = check_pointer(val, maplist)

                    if dst:
                        offset, dstseg = dst
                        memgraph[region[2]][dstseg].append((addr - region[0], offset))

                    raw_mem = f.read(8)
                    addr += 8

    return memgraph


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
def gdb_main(pid, sources=None, online=True, name="", dump=False, llb = -1, lub=2**30, numberby=0):
    maplist = build_maplist(pid, numberby)
    if online:
        memgraph = build_graph(maplist, sources=sources, dump=dump, dumpname=name, length_lb=llb, length_ub=lub)
    else:
        dump_mem(maplist, sources=sources, dumpname=name, length_lb=llb, length_ub=lub)
        memgraph = build_graph_from_dumps(maplist, sources=sources, dumpname=name, length_lb=llb, length_ub=lub)
    with open(name + "memgraph.pickle", "wb") as f:
        pickle.dump(memgraph, f)
    with open(name + "maplist.pickle", "wb") as f2:
        pickle.dump(maplist, f2)
    gdb.execute("detach")
    gdb.execute("quit")