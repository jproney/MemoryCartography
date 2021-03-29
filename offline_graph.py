import os
import pickle
import argparse
import struct

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

def build_graph_from_dumps(maplist, pointer_sz=8, sources=None, dumpname="", length_lb = -1, length_ub = 2**30):
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
                raw_mem = f.read(pointer_sz)

                while raw_mem:
                    val = int.from_bytes(raw_mem, "little")
                    dst = check_pointer(val, maplist)

                    if dst:
                        offset, dstseg = dst
                        memgraph[region[2]][dstseg].append((addr - region[0], offset))

                    raw_mem = f.read(pointer_sz)
                    addr += pointer_sz

    return memgraph

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