import pickle
import struct 
import numpy as np
import argparse
import os
import re
import tempfile
import itertools
import math

parser = argparse.ArgumentParser()
parser.add_argument("dir", help="output directory to analyze (created by runing harvest_heap_data.py)")
parser.add_argument("--rank", type=int, default=0, help="An integer representing the index of the pointer to target, with 0 representing the most frequent.")
parser.add_argument("--heap_idx", type=int, default=0, help="An integer representing the index of the heap we are interested in, in descending order of size.")
args = parser.parse_args()

# list of memory graph data structures. Store lists of outgoing pointers from some number of source regions
graphfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith("memgraph.pickle")])
memgraphs = [pickle.load(open(gf, "rb")) for gf in graphfiles]

# list of data structures containing all mapped regions in the target process
mapfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith("maplist.pickle")])
maplists = [pickle.load(open(mf, "rb")) for mf in mapfiles]

# the names which prefix al of the files for each run
runnames = [x[len(args.dir):].split("_")[0] for x in mapfiles]

heapfiles = []
heapnames = []
dumpfiles = []
heaps = []
for r in runnames:
    dumpfiles.append(sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith(".dump") and f.split("_")[0] == r]))
    heapnames.append(["_".join(x[len(args.dir):].split("_")[1:])[:-5] for x in dumpfiles[-1]])
    heaps.append([open(args.dir + r + "_"+ h + ".dump", 'rb') for h in heapnames[-1]])



def read_heap_bytes(heapfile, offset, nbytes):
    heapfile.seek(offset)
    return heapfile.read(nbytes)

def read_heap_pointer(heapfile, offset):
    heapfile.seek(offset)
    return struct.unpack('P', heapfile.read(8))[0]

def read_heap_int(heapfile, offset):
    heapfile.seek(offset)
    return struct.unpack('<i', heapfile.read(4))

pointerdict = {}
mapdicts = []

# Get statistics about which pointer destinations are most frequent across all runs
for i in range(len(heaps)):
    md = {}
    for reg in maplists[i]:
        md[reg[2]] = (reg[0], reg[1])

    mapdicts.append(md)

    for heapname in heapnames[i]:
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
addrs = [[sorted([md[h][0] + edge[0] for edge in mg[h][section] if edge[1] == dst_offset])  
            for h in hps]
                for md,mg,hps in zip(mapdicts, memgraphs, heapnames)]

mindist = min([addrs[i][j][k+1] - addrs[i][j][k] for i in range(len(addrs)) for j in range(len(addrs[i])) for k in range(0, len(addrs[i][j])-1)])

aln = 8
aln_offset = 0
while all([a%(aln*2) == addrs[0][0][0]%(aln*2) for run in addrs for hp in run for a in hp]) and aln < mindist:
    aln *= 2
    aln_offset = addrs[0][0][0]%aln

# Read two alignment's-worth of data behind and in front of the aligned pointer address (heuristic choice)
preread = 32
postread = 32

# Find lower and upper bounds
lbs = np.zeros([len(heaps), preread+postread])
ubs = np.zeros([len(heaps), preread+postread])
for i in range(len(heaps)):
    addresses_agg = [(h,a) for h in range(len(addrs[i])) for a in addrs[i][h] 
                                                            if a - mapdicts[i][heapnames[i][h]][0] >= preread
                                                                and a <= mapdicts[i][heapnames[i][h]][1] - postread]
    prints = np.zeros([len(addresses_agg), preread+postread])
    for j,(h,a) in enumerate(addresses_agg):
        prints[j]  = np.array([x for x in read_heap_bytes(heaps[i][h], a - mapdicts[i][heapnames[i][h]][0] - preread, (preread + postread))])
    np.set_printoptions(threshold=np.inf)

    lbs[i]  = prints.min(axis=0)
    ubs[i]  = prints.max(axis=0)

# print(lbs)
# print(ubs)


# perform leave-one-out cross-validation:
grand_total_true = 0
grand_total = 0
grand_tp = 0
grand_fp =0
minpres = []
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
    total_addrs = 0
    total_true = 0
    local_pres = []
    for j,heapname in enumerate(heapnames[i]):
        local_tp = []
        local_fp = []
        for offset in range(math.ceil(preread/aln)*aln + aln_offset, mapdicts[i][heapname][1] - mapdicts[i][heapname][0] - postread, aln):
            dat = np.array([x for x in read_heap_bytes(heaps[i][j], offset - preread, (preread + postread))])
            if all(lb2 <= dat) and all(dat <= ub2):
                if mapdicts[i][heapname][0] + offset in addrs[i][j]:
                    trupos.append((j,offset))
                    local_tp.append(offset)
                else:
                    falsepos.append((j,offset))
                    local_fp.append(offset)
        print("HEAP {}: TPS: {}/{} FPS: {}/{}".format(j, len(local_tp), len(addrs[i][j]), len(local_fp), (mapdicts[i][heapname][1] - mapdicts[i][heapname][0])//aln - len(addrs[i][j])))
        if (len(local_tp) + len(local_fp)) > 0:
            local_pres.append(len(local_tp)/(len(local_tp) + len(local_fp)))
        else:
            local_pres.append(0)
        total_addrs += (mapdicts[i][heapname][1] - mapdicts[i][heapname][0])//aln 
        total_true += len(addrs[i][j])
    minpres.append(min(local_pres))
    print("TPR: {} ({}/{})".format(len(trupos)/total_true, len(trupos), total_true))
    print("FPR: {} ({}/{})".format(len(falsepos)/(total_addrs - total_true), len(falsepos), total_addrs - total_true))
    grand_total += total_addrs
    grand_total_true += total_true
    grand_tp += len(trupos)
    grand_fp += len(falsepos)
# Create and save the master bounds
lb_final = np.clip(lbs.min(axis=0) - (lbs.max(axis=0) - lbs.min(axis=0)), 0, 255)
ub_final = np.clip(ubs.max(axis=0) + (ubs.max(axis=0) - ubs.min(axis=0)), 0, 255)
pickle.dump((lb_final, ub_final, section, dst_offset, aln, aln_offset), open(args.dir + "classifier_{}_{}.pickle".format(section.split("/")[-1], dst_offset), 'wb'))
print("TOTAL TPR: {} ({}/{})".format(grand_tp/grand_total_true, grand_tp, grand_total_true))
print("TOTAL FPR: {} ({}/{})".format(grand_fp/(grand_total - grand_total_true), grand_fp, grand_total - grand_total_true))
print(section)
print(dst_offset)
print(minpres)
print(sum(minpres)/len(minpres))