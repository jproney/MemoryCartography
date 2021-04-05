import os
import pickle
import argparse
import struct
import data_structures


def build_graph_from_dumps(maplist, pointer_sz=8, sources=None, dumpname="", length_lb = -1, length_ub = 2**30):
    
    nodelist = [reg.name for reg in maplist.regions_list]
    sourcelist = [reg.name for reg in maplist.regions_list if reg.end - reg.start >= length_lb and reg.end - reg.start <= length_ub]
    if sources:
        sourcelist = [s for s in sourcelist if s in sources]

    memgraph = data_structures.MemoryGraph(nodelist, sourcelist)

    for i,src in enumerate(sourcelist):
        # Same deal as using gdb, just read from dumps instead
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
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", help="directory to be analyzed")
    parser.add_argument("--n", type=int, default=10, help="number of runs")
    parser.add_argument("--pointer_sz", type=int, default=8, help="Length of a pointer in memory being analyzed")
    parser.add_argument("--sources", nargs="+", default=[], help="Heap regions to exclude from analysis")
    args = parser.parse_args()


    ml = [pickle.load(open("{}/run{}_maplist.pickle".format(args.dir, i), "rb")) for i in range(args.n)]
    mg = [build_graph_from_dumps(ml[i], pointer_sz=args.pointer_sz, sources= args.sources if len(args.sources) > 0 else None, dumpname="{}/run{}_".format(args.dir, i)) for i in range(args.n)]

    for i in range(args.n):
        pickle.dump(mg[i], open("{}/run{}_memgraph.pickle".format(args.dir, i), "wb"))