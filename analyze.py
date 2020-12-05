import pickle
import struct 
import numpy as np
import argparse
import os
import re

parser = argparse.ArgumentParser()
parser.add_argument("dir", help="output directory to analyze (created by runing harvest_heap_data.py)")
args = parser.parse_args()

dumpfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith(".dump")])
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

(section, offset), nobs = pointerlist[0]
addrs = [sorted([md[heapname][0] + edge[0] for edge in mg[heapname][section] if edge[1] == offset]) for md,mg in zip(mapdicts, memgraphs)]

# Find the minimum distance between any two pointers of interest 
mindist = min([min([addrs[i][j+1] - addrs[i][j] for j in range(0, len(addrs[i])-1)]) for i in range(len(addrs))])

# Assume pointers live in a struct and determine its alignment
aln = 8
while all([a%(aln*2) == addrs[0][0]%(aln*2) for run in addrs for a in run]) and aln < mindist:
    aln *= 2

# Read two alignment's-worth of data behind and in front of the aligned pointer address (heuristic choice)
preread = 2
postread = 2

prints = np.zeros([nobs, 4*aln])
row=0
for i in range(len(heaps)):
    for j,a in enumerate(addrs[i]):
        base = (a//aln) * aln
        prints[row,:]  = np.array([x for x in read_heap_bytes(heaps[i], base - mapdicts[i][heapname][0] - preread*aln, (preread + postread)*aln)])
        row += 1

# Record a range of observed values for each byte in the observed range
lbs = prints.min(axis=0)
ubs = prints.max(axis=0)

# Test the accuracy of pointer fingerprinting on the test data
trupos = []
falsepos = []
for i in range(len(heaps)):
    for offset in range(preread*aln, mapdicts[i][heapname][1] - mapdicts[i][heapname][0] - postread*aln, aln):
        dat = np.array([x for x in read_heap_bytes(heaps[i], offset - preread*aln, (preread + postread)*aln)])
        if all(lbs <= dat) and all(dat <= ubs):
            if mapdicts[i][heapname][0] + offset in addrs[i]:
                trupos.append(offset)
            else:
                falsepos.append(offset)

total_addrs = sum([(md[heapname][1] - md[heapname][0])//aln for md in mapdicts])
total_true = sum([len(a) for a in addrs])
print("TPR: {}".format(len(trupos)/total_true))
print("FPR: {}".format(len(falsepos)/(total_addrs - total_true)))
pickle.dump((lbs, ubs, section, offset), open(args.dir + "classifier.pickle", 'wb'))