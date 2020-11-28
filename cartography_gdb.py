"""
Map out allocated memory regions in a specificed binary.
Example usage:
gdb -x cartography_gdb.py -ex 'py gdb_main("tests/harvest_pointers.out", 16, [])'
"""

import gdb #won't work unless script is being run under a GDB process
import re
import pickle

"""
Construct list of contiguous mapped regions, their offsets, and their names
"""
def build_maplist(executable, break_line, program_args):
    gdb.execute("file " + executable + " " + " ".join(program_args))
    if break_line > 0:
        gdb.execute("break " + str(break_line))
    gdb.execute("run")

    # At breakpoint. Get the addresses of all of the mapped memory regions
    maps = [re.split(r'\s{1,}', s)[1:] for s in gdb.execute("info proc mappings", False, True).split("\n")[4:-1]]
    mapdict={}  #each dict entry is a list of tuples with start and end of each mapped range
    for segment in maps:
        segname = segment[-1]
        if segname in ["[vvar]", "[vdso]", "[vsyscall]","", "(deleted)"] or segname.split(".")[-1] in ["ttf", "ja"]: #ignore these regions
            continue
        if segname not in mapdict:
            mapdict[segname] = [(int(segment[0],16), int(segment[1],16))]
        else:
            if int(segment[0], 16) == mapdict[segname][-1][1]: #comibine adjascent memory ranges into one range
                mapdict[segname][-1] = (mapdict[segname][-1][0], int(segment[1], 16))
            else:
                mapdict[segname].append((int(segment[0],16), int(segment[1],16)))
        
    maplist=[] #flat version of mapped memory reigons. List of tuples of form (name, start, end)
    for seg in mapdict.keys():
        for i,reg in enumerate(mapdict[seg]):
            maplist.append((reg[0], reg[1], seg + "_" + str(i)))

    return maplist


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
def build_graph(maplist):
    memgraph = {} #adjacency matrix, where entry [i][j] is a list of (src_offset, dst_offset) links between regions i and j
    for  _, _, name_i in maplist:
        memgraph[name_i] = {}
        for _,_, name_j in maplist:
            memgraph[name_i][name_j] = [] 

    for i,region in enumerate(maplist):
        print("Scanning " + str(region) + " ({}/{})".format(i,len(maplist)) + "len = {} bytes".format(region[1] - region[0]))
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
                if dstseg != region[2]: #add edges between different regions
                    # edge representation = (src_offset, dst_offset)
                    memgraph[region[2]][dstseg].append((addr - region[0], offset))

    return memgraph

"""
Run the full script and save the memory graph
"""
def gdb_main(executable, break_line, program_args):
    maplist = build_maplist(executable, break_line, program_args)
    memgraph = build_graph(maplist)
    with open("memgraph.pickle", "wb") as f:
        pickle.dump(memgraph, f)
    gdb.execute("detach")
    gdb.execute("quit")