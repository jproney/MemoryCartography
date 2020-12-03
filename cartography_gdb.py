"""
Map out allocated memory regions in a specificed binary.
Example usage:
gdb -x cartography_gdb.py -ex 'py gdb_main(5201, ["[heap]_0"], True)'
"""

import gdb #won't work unless script is being run under a GDB process
import re
import pickle

"""
Construct list of contiguous mapped regions, their offsets, and their names
"""
def build_maplist(pid):
    gdb.execute("attach " + str(pid))

    # At breakpoint. Get the addresses of all of the mapped memory regions
    maps = [re.split(r'\s{1,}', s)[1:] for s in gdb.execute("info proc mappings", False, True).split("\n")[4:-1]]
    mapdict={}  #each dict entry is a list of tuples with start and end of each mapped range
    for segment in maps:
        segname = segment[-1]
        if segname == "(deleted)":
            segname = segment[-2] + "_(deleted)"
        if segname not in mapdict:
            mapdict[segname] = [(int(segment[0],16), int(segment[1],16))]
        else:
            if int(segment[0], 16) == mapdict[segname][-1][1]: #comibine adjascent memory ranges into one range
                mapdict[segname][-1] = (mapdict[segname][-1][0], int(segment[1], 16))
            else:
                mapdict[segname].append((int(segment[0],16), int(segment[1],16)))
        
    maplist=[] #flat version of mapped memory reigons. List of tuples of form (start, end, name)
    for seg in mapdict.keys():
        for i,reg in enumerate(mapdict[seg]):
            maplist.append((reg[0], reg[1], seg + "_" + str(i)))
    print(maplist)
    return sorted(maplist, key = lambda x: x[0])


"""
Check whether address is mapped
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
Build the Memory Cartography graph
"""
def build_graph(maplist, sources=None, fulldump=False): #sources = list of source ranges to scan, if None, scan everything, fulldump = dump all of the source regions
    memgraph = {} #adjacency matrix, where entry [i][j] is a list of (src_offset, dst_offset) links between regions i and j
    sourcelist = [x for x in maplist if x[2] in sources] if sources else maplist
    for  _, _, name_i in sourcelist:
        memgraph[name_i] = {}
        for _,_, name_j in maplist:
            memgraph[name_i][name_j] = [] 

    for i,region in enumerate(sourcelist):
        print("Scanning " + str(region) + " ({}/{})".format(i,len(sourcelist)) + "len = {} bytes".format(region[1] - region[0]))
        if fulldump:
            gdb.execute("dump memory {}.dump {} {}".format(region[2], region[0], region[1]))
        for addr in range(region[0], region[1]-7):
            if (addr - region[0]) % ((region[1] - region[0])//10) == 0:
                print("{}%".format(10*(addr - region[0]) / ((region[1] - region[0])//10)))
            try:
                val = int(gdb.execute("x/g " + str(addr), False, True).split()[-1])
            except:
                continue
            dst = check_pointer(val, maplist)
            if dst:
                offset, dstseg = dst
                memgraph[region[2]][dstseg].append((addr - region[0], offset))
    return memgraph

"""
Run the full script and save the memory graph
"""
def gdb_main(pid, sources=None, dump=False):
    maplist = build_maplist(pid)
    memgraph = build_graph(maplist, sources, dump)
    with open("memgraph.pickle", "wb") as f:
        pickle.dump(memgraph, f)
    with open("maplist.pickle", "wb") as f2:
        pickle.dump(maplist, f2)
    gdb.execute("detach")
    gdb.execute("quit")