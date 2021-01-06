import pickle
import struct 
import numpy as np
import argparse
import os
import re

parser = argparse.ArgumentParser()
parser.add_argument("dir", help="output directory to analyze (created by runing harvest_heap_data.py)")
parser.add_argument("--rank", type=int, default=0, help="An integer representing the index of the pointer to target, with 0 representing the most frequent.")
parser.add_argument("--heap_idx", type=int, default=0, help="An integer representing the index of the heap we are interested in, in descending order of size.")
args = parser.parse_args()

# Filter out only heap_idx
dumpfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith("{}.dump".format(args.heap_idx))])
heaps = [open(df, "rb") for df in dumpfiles]


graphfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith("memgraph.pickle")])
memgraphs = [pickle.load(open(gf, "rb")) for gf in graphfiles]

mapfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith("maplist.pickle")])
maplists = [pickle.load(open(mf, "rb")) for mf in mapfiles]


def read_heap_bytes(heapfile, offset, nbytes):
    heapfile.seek(offset)
    return heapfile.read(nbytes)

def read_heap_pointer(heapfile, offset):
    heapfile.seek(offset)
    return struct.unpack('P', heapfile.read(8))[0]

def read_heap_int(heapfile, offset):
    heapfile.seek(offset)
    return struct.unpack('<i', heapfile.read(4))

heapname = "_".join(dumpfiles[0].split("_")[-2:])[:-5]

pointerdict = {}
mapdicts = []

# Get statistics about which pointer destinations are most frequent across all runs
for i in range(len(heaps)):
    md = {}
    for reg in maplists[i]:
        md[reg[2]] = (reg[0], reg[1])

    mapdicts.append(md)

    for dst in memgraphs[i][heapname].keys():
        for ptr in memgraphs[i][heapname][dst]:
            if (dst, ptr[1]) in pointerdict:
                pointerdict[(dst, ptr[1])] += 1
            else:
                pointerdict[(dst, ptr[1])] = 1
          

pointerlist = sorted(pointerdict.items(), key=lambda item: item[1], reverse=True)

# Starting with the most frequent, look for "fingerprints" surrounding the pointers

(section, dst_offset), nobs = pointerlist[args.rank]

# Addrs is list of lists of pointers found in each run
addrs = [sorted([md[heapname][0] + edge[0] for edge in mg[heapname][section] if edge[1] == dst_offset]) for md,mg in zip(mapdicts, memgraphs)]

# Find the minimum distance between any two pointers of interest 
# Ignores when addrs[i] is of length 0
mindist = min([min([addrs[i][j+1] - addrs[i][j] for j in range(0, len(addrs[i])-1)]) for i in range(len(addrs)) if len(addrs[i]) > 0] )

# Assume pointers live in a struct and determine its alignment
aln = 8
while all([a%(aln*2) == addrs[0][0]%(aln*2) for run in addrs for a in run]) and aln < mindist:
    aln *= 2

# Read two alignment's-worth of data behind and in front of the aligned pointer address (heuristic choice)
preread = 2
postread = 2

# Find lower and upper bounds
lbs = np.zeros([len(heaps), aln*4])
ubs = np.zeros([len(heaps), aln*4])
for i in range(len(heaps)):
    prints = np.zeros([len(addrs[i]), aln*4])
    for j,a in enumerate(addrs[i]):
        base = (a//aln) * aln
        prints[j]  = np.array([x for x in read_heap_bytes(heaps[i], base - mapdicts[i][heapname][0] - preread*aln, (preread + postread)*aln)])

    lbs[i]  = prints.min(axis=0)
    ubs[i]  = prints.max(axis=0)


# perform leave-one-out cross-valitation:
for i in range(len(heaps)):

    print("Cross Validation: Holding out run {}".format(i))
    # exclude the bounds from the held-out run
    lb_val = np.delete(lbs, i, axis=0)
    ub_val = np.delete(ubs, i, axis=0)

    # Widen intervals for positions where bounds vary accross runs
    lb2 = np.clip(lb_val.min(axis=0) - (lb_val.max(axis=0) - lb_val.min(axis=0)), 0, 255)
    ub2 = np.clip(ub_val.max(axis=0) + (ub_val.max(axis=0) - ub_val.min(axis=0)), 0, 255)

    # Test the accuracy of pointer fingerprinting on the test data
    trupos = []
    falsepos = []
    for offset in range(preread*aln, mapdicts[i][heapname][1] - mapdicts[i][heapname][0] - postread*aln, aln):
        dat = np.array([x for x in read_heap_bytes(heaps[i], offset - preread*aln, (preread + postread)*aln)])
        if all(lb2 <= dat) and all(dat <= ub2):
            if mapdicts[i][heapname][0] + offset in addrs[i]:
                trupos.append(offset)
            else:
                falsepos.append(offset)

    total_addrs = (mapdicts[i][heapname][1] - mapdicts[i][heapname][0])//aln 
    total_true = len(addrs[i])
    print("TPR: {} ({}/{})".format(len(trupos)/total_true, len(trupos), total_true))
    print("FPR: {} ({}/{})".format(len(falsepos)/(total_addrs - total_true), len(falsepos), total_addrs - total_true))

# Create and save the master bounds
lb_final = np.clip(lbs.min(axis=0) - (lbs.max(axis=0) - lbs.min(axis=0)), 0, 255)
ub_final = np.clip(ubs.max(axis=0) + (ubs.max(axis=0) - ubs.min(axis=0)), 0, 255)
pickle.dump((lb_final, ub_final, section, dst_offset), open(args.dir + "classifier_{}_{}.pickle".format(section.split("/")[-1], dst_offset), 'wb'))
