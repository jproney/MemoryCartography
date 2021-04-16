import os
import argparse
import struct
import data_structures


"""
Build a series of memory dumps from a process into a memory graph of pointers between regions
maplist = data_structures.MapList object containing the VMAs of the target process
pointer_sz = number of bytes per pointer in the memory dumpes
sources = list of names of regions to be scanned for pointers
length_lb = lower bound on the length of regions to be scanned for pointers
length_ub = upper bound on the length of regions to be scanned for pointers
"""
def build_graph_from_dumps(maplist, pointer_sz=8, sources=None, dumpname="", length_lb = -1, length_ub = 2**30):
    
    nodelist = [reg.name for reg in maplist.regions_list]
    sourcelist = [reg.name for reg in maplist.regions_list if reg.end - reg.start >= length_lb and reg.end - reg.start <= length_ub]
    if sources:
        sourcelist = [s for s in sourcelist if "_".join(s.split("_")[:-1]) in sources]

    memgraph = data_structures.MemoryGraph(nodelist, sourcelist)

    for i,src in enumerate(sourcelist):
        print("Scanning " + str(src) + " ({}/{})".format(i,len(sourcelist)))

        if os.path.exists("{}.dump".format(dumpname + src.split("/")[-1])):
            with open("{}.dump".format(dumpname + src.split("/")[-1]), "rb") as f:

                offset = 0
                raw_mem = f.read(pointer_sz)
                while raw_mem:
                    val = int.from_bytes(raw_mem, "little")
                    dst = maplist.check_pointer(val)

                    if dst:
                        memgraph.add_edge(src, dst.name, offset, val - dst.start)

                    raw_mem = f.read(pointer_sz)
                    offset += pointer_sz

    return memgraph
    
"""    
Build a memory graph from a series of dumps files that were produced by a previous run of harvest_heap_data.py
"""
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", help="directory to be analyzed")
    parser.add_argument("--n", type=int, default=10, help="number of runs")
    parser.add_argument("--pointer_sz", type=int, default=8, help="Length of a pointer in memory being analyzed")
    parser.add_argument("--sources", nargs="+", default=[], help="Heap regions to exclude from analysis")
    args = parser.parse_args()


    ml = [data_structures.MapList().deserialize("{}/run{}_maplist.json".format(args.dir, i)) for i in range(args.n)]
    mg = [build_graph_from_dumps(ml[i], pointer_sz=args.pointer_sz, sources= args.sources if len(args.sources) > 0 else None, dumpname="{}/run{}_".format(args.dir, i)) for i in range(args.n)]

    for i in range(args.n):
        mg[i].serialize("{}/run{}_memgraph.json".format(args.dir, i))