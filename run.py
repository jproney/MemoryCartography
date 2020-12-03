"""
Run the memory cartography code! Example usage:
python run.py tests/harvest_pointers.out 16
Dumps the final memory graph into memgraph.pickle
"""

import argparse
import os
import pickle

parser = argparse.ArgumentParser()
parser.add_argument("binary", help="the binary to build memory map off of")
parser.add_argument("--break_line", type=int, default=0, help="Which line of the binary to break on? Default waits for user to break")
parser.add_argument("--num_repeats",type=int, default=3, help="How many times to rebuild the graph to eliminate false positives")
parser.add_argument("--binary_args", nargs="*", default=[], help="arguments for the input binary")
args = parser.parse_args()

mg = None
for i in range(args.num_repeats):
    print("Building Map: Round {}".format(i))
    os.system("gdb -x cartography_gdb.py -ex 'py gdb_main(\"{}\", {}, {})'".format(args.binary, args.break_line, args.binary_args))
    with open("memgraph.pickle", "rb") as f:
        newmg = pickle.load(f)
        if mg:
            for src in mg.keys():
                for dst in mg[src].keys():
                    edgelist = mg[src][dst]
                    newlist = []
                    for e in edgelist:
                        if e in newmg[src][dst]:
                            newlist.append(e)
                    mg[src][dst] = newlist
        else:
            mg = newmg
with open("memgraph.pickle","wb") as f:
    pickle.dump(mg,f)