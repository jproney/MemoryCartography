"""
Analyze the results of heap dumps produced by harvest_heap_data.py. See parser for arguments.
All dump files in the input directory will be treated as heaps and analyzed.
Example usage: python analyze.py vim_heap_analysis --rank 0
"""


import pickle
import struct 
import numpy as np
import argparse
import os
import re
import tempfile
import itertools
import math
import struct


parser = argparse.ArgumentParser()
parser.add_argument("dir", help="output directory to analyze (created by runing harvest_heap_data.py)")
parser.add_argument("--rank", type=int, default=0, help="An integer representing the index of the pointer to target, with 0 representing the most frequent.")
parser.add_argument("--pointer_sz", type=int, default=8, help="Length of a pointer in memory being analyzed")
parser.add_argument("--exclude_src", nargs="+", default=[], help="Heap regions to exclude from analysis")
parser.add_argument("--exclude_dst", nargs="+", default=[], help="Exclude these pointer destinations")
parser.add_argument("--save", dest='save', action='store_true', help="Save the filter bounds")
parser.add_argument("--print_offsets", action='store_true', help="print the offsets of the pointers")
parser.add_argument("--nohold", action='store_true', help="Don't hold out and just look at training set accuracy (sanity check, TPRs should be 1.0)")
args = parser.parse_args()

# list of memory graph data structures. Store lists of outgoing pointers from some number of source regions
graphfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith("memgraph.pickle")])
memgraphs = [pickle.load(open(gf, "rb")) for gf in graphfiles]

# list of data structures containing all mapped regions in the target process
mapfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith("maplist.pickle")])
maplists = [pickle.load(open(mf, "rb")) for mf in mapfiles]

# the names which prefix al of the files for each run
runnames = [x[len(args.dir):].split("_")[0] for x in mapfiles]

heapfiles = [] #file handles for all of the heaps. 2D list. Outer dimension is run, inner dimension is individual heap region
heapnames = [] #name of each heap as seen in maplist and memgraph. 2D list. Outer dimension is run, inner dimension is individual heap region
dumpfiles = [] #dump file names for all heaps. 2D list. Outer dimension is run, inner dimension is individual heap region
heaps = []
for r in runnames:
    # package all dump files ending in the string `r` as belonging to different regions from the same run
    dumpfiles.append(sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith(".dump") and f.split("_")[0] == r and "_".join(f.split("_")[1:])[:-5] not in args.exclude_src]))
    heapnames.append(["_".join(x[len(args.dir):].split("_")[1:])[:-5] for x in dumpfiles[-1]])
    heaps.append([open(args.dir + r + "_"+ h + ".dump", 'rb') for h in heapnames[-1]])

print(dumpfiles)

# Utility functions for reading things from the heap dumps
def read_heap_bytes(heapfile, offset, nbytes):
    heapfile.seek(offset)
    return heapfile.read(nbytes)

def read_heap_pointer(heapfile, offset):
    heapfile.seek(offset)
    return struct.unpack('P', heapfile.read(args.pointer_sz))[0]

def read_heap_int(heapfile, offset):
    heapfile.seek(offset)
    return struct.unpack('<i', heapfile.read(4))


mapdicts = [] # List of dictionaries, one for each run. Dictionaries simply map a region name to its start and end for more convenient retrieval.
for i in range(len(runnames)):
    md = {}
    for reg in maplists[i]:
        md[reg[2]] = (reg[0], reg[1])

    mapdicts.append(md)


pointerdict = {} # dictionary mapping from (region, offset) pairs to frequencies accross each heap region

# Get statistics about which pointer destinations are most frequent across all heaps and all runs
for i in range(len(runnames)): # iterate over runs
    for heapname in heapnames[i]: # iterate over heaps within run
        for dst in memgraphs[i][heapname].keys(): # iterate over possible pointer destinations
            for ptr in memgraphs[i][heapname][dst]: # iterate over all pointers from run i, heap j, to region dst. Recall ptr is a (src_offset, dst_offset) tuple
                if (dst, ptr[1]) in pointerdict:
                    pointerdict[(dst, ptr[1])][i] += 1
                else:
                    pointerdict[(dst, ptr[1])] = [0]*len(runnames)
                    pointerdict[(dst, ptr[1])][i] = 1
          

pointerlist = sorted(pointerdict.items(), key=lambda item: sum(item[1]), reverse=True)
pointerlist = [x for x in pointerlist if x[0][0] not in args.exclude_dst]

# Look for "fingerprints" surrounding the pointers

(section, dst_offset), nobs = pointerlist[args.rank] # just analyze the pointer of the rank specified by the user

print((section, dst_offset))

# Addrs is double-list containing addresses of the pointer of interst. Outer dimension is across runs, inner is accross heap regions.
addrs = [[sorted([md[h][0] + edge[0] for edge in mg[h][section] if edge[1] == dst_offset]) for h in hps] for md,mg,hps in zip(mapdicts, memgraphs, heapnames)]
min_number = min([sum([len(h) for h in r]) for r in addrs]) #The lowest number of times the pointer occurs in any run
if min_number == 0:
    exit("Pointer of rank {} not found in all runs. Try another pointer.".format(args.rank))

# get the minimum distance between any 2 pointers
mindist = min([addrs[i][j][k+1] - addrs[i][j][k] for i in range(len(addrs)) for j in range(len(addrs[i])) for k in range(0, len(addrs[i][j])-1)])

aln = args.pointer_sz
aln_offset = 0

ref = min([x for a in addrs[0] for x in a]) # get a reference pointer for computing the offsets of the poitners
while all([a%(aln*2) == ref%(aln*2) for run in addrs for hp in run for a in hp]) and aln < mindist:
    aln *= 2
    aln_offset = ref%aln

# Read 32 bytes of data behind and in front of the aligned pointer address (heuristic choice)
preread = 32
postread = 32

# Find lower and upper bounds for the data surround the pointers of interest. 
# Maintain bounds separately for the data from each run in order to identify elemnts that vary across runs and therefore 
# need to be treated differently. Mainting separate bounds for each run also allows for cross validation.
lbs = np.zeros([len(runnames), preread+postread])
ubs = np.zeros([len(runnames), preread+postread])
for i in range(len(runnames)):
    # list of all addresses in this run in form (heap_index, address). List aggregates addresses from all heaps.
    addresses_agg = [(h,a) for h in range(len(heapnames[i])) for a in addrs[i][h] 
                                                            if a - mapdicts[i][heapnames[i][h]][0] >= preread
                                                                and a <= mapdicts[i][heapnames[i][h]][1] - postread]
    prints = np.zeros([len(addresses_agg), preread+postread])
    for j,(h,a) in enumerate(addresses_agg):
        prints[j]  = np.array([x for x in read_heap_bytes(heaps[i][h], a - mapdicts[i][heapnames[i][h]][0] - preread, (preread + postread))])

    lbs[i] = prints.min(axis=0)
    ubs[i] = prints.max(axis=0)


# perform leave-one-out cross-validation:
grand_total_true = 0 # total true pointers across all hepas and runs
grand_total_addrs = 0 # total number of addresses in all of the heaps and runs
grand_tp = 0 # total true positives across all heaps and runs
grand_fp =0 # total false positives across all heaps and runs
minprec = [] # lowest precision of any heap region for each run

for i in range(len(runnames)):

    print("Cross Validation: Holding out run {}".format(i))

    # exclude the bounds from the held-out run
    if args.nohold:
        lb2 = lbs.min(axis=0)
        ub2 = ubs.max(axis=0)
    else:
        lb_val = np.delete(lbs, i, axis=0)
        ub_val = np.delete(ubs, i, axis=0)

        # Widen intervals for positions where bounds vary accross runs
        lb2 = np.clip(lb_val.min(axis=0) - (lb_val.max(axis=0) - lb_val.min(axis=0)), 0, 255)
        ub2 = np.clip(ub_val.max(axis=0) + (ub_val.max(axis=0) - ub_val.min(axis=0)), 0, 255)

    # Test the accuracy of pointer fingerprinting on the test data

    # Statistics for this particular hold-out run
    current_run_trupos = []
    current_run_falsepos = []
    current_run_total_addrs = 0
    current_run_total_true = 0
    local_prec = [] # precision evaluated on each held-out heap region

    for j,heapname in enumerate(heapnames[i]):
        # tp and fp statistics for this held-out heap
        current_heap_tp = []
        current_heap_fp = []

        # scan positions that conform to the alignment rules. We should be able to get the correct alignment off of the training samples, so we shouldn't need to 
        # bother with other positions
        for offset in range(math.ceil(preread/aln)*aln + aln_offset, mapdicts[i][heapname][1] - mapdicts[i][heapname][0] - postread, aln):
            dat = np.array([x for x in read_heap_bytes(heaps[i][j], offset - preread, (preread + postread))]) #read data from the heap
            if all(lb2 <= dat) and all(dat <= ub2):
                if mapdicts[i][heapname][0] + offset in addrs[i][j]:
                    current_run_trupos.append((j,offset))
                    current_heap_tp.append(offset)
                else:
                    current_run_falsepos.append((j,offset))
                    current_heap_fp.append(offset)

        print("HEAP {}: TPS: {}/{} FPS: {}/{}".format(j, len(current_heap_tp), len(addrs[i][j]), len(current_heap_fp), (mapdicts[i][heapname][1] - mapdicts[i][heapname][0])//aln - len(addrs[i][j])))

        if args.print_offsets:
            print(current_heap_tp)

        # Conditional avoids division by zero
        if (len(current_heap_tp) + len(current_heap_fp)) > 0:
            local_prec.append(len(current_heap_tp)/(len(current_heap_tp) + len(current_heap_fp)))
        else:
            local_prec.append(0)

        current_run_total_addrs += (mapdicts[i][heapname][1] - mapdicts[i][heapname][0])//aln 
        current_run_total_true += len(addrs[i][j])
    minprec.append(min(local_prec)) # precision of the worst heap in this run

    print("TPR: {} ({}/{})".format(len(current_run_trupos)/current_run_total_true, len(current_run_trupos), current_run_total_true))
    print("FPR: {} ({}/{})".format(len(current_run_falsepos)/(current_run_total_addrs - current_run_total_true), len(current_run_falsepos), current_run_total_addrs - current_run_total_true))
    grand_total_addrs += current_run_total_addrs
    grand_total_true += current_run_total_true
    grand_tp += len(current_run_trupos)
    grand_fp += len(current_run_falsepos)

# Create and save the master bounds
lb_final = np.clip(lbs.min(axis=0) - (lbs.max(axis=0) - lbs.min(axis=0)), 0, 255)
ub_final = np.clip(ubs.max(axis=0) + (ubs.max(axis=0) - ubs.min(axis=0)), 0, 255)
if args.save:
    pickle.dump((lb_final, ub_final, section, dst_offset, aln, aln_offset), open(args.dir + "classifier_{}_{}.pickle".format(section.split("/")[-1], dst_offset), 'wb'))
print("TOTAL TPR: {} ({}/{})".format(grand_tp/grand_total_true, grand_tp, grand_total_true))
print("TOTAL FPR: {} ({}/{})".format(grand_fp/(grand_total_addrs - grand_total_true), grand_fp, grand_total_addrs - grand_total_true))
print("TOTAL PRECISION: {}".format(grand_tp / (grand_tp + grand_fp)))
print("TARGET REGION: {}".format(section))
print("OFFSET: {}".format(dst_offset))
print("POINTER ALIGNMENT: {}".format(aln))
print("AVERAGE WORST-CASE PRECISION: {}".format(sum(minprec)/len(minprec))) # average precision in the worst region