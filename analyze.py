"""
Analyze the results of heap dumps produced by harvest_heap_data.py. See parser for arguments.
All dump files in the input directory will be treated as heaps and analyzed.
Example usage: python analyze.py vim_heap_analysis --rank 0
"""


import numpy as np
import os
import argparse
import re
import tempfile
import itertools
import math
import struct
from data_structures import RunContainer, MapList, MemoryGraph


parser = argparse.ArgumentParser()
parser.add_argument("dir", help="output directory to analyze (created by runing harvest_heap_data.py)")
parser.add_argument("--rank", type=int, default=0, help="An integer representing the index of the pointer to target, with 0 representing the most frequent.")
parser.add_argument("--preread", type=int, default=32, help="Number of window bytes before pointer address")
parser.add_argument("--postread", type=int, default=32, help="Number of window bytes after pointer address")
parser.add_argument("--pointer_sz", type=int, default=8, help="Length of a pointer in memory being analyzed")
parser.add_argument("--exclude_src", nargs="+", default=[], help="Heap regions to exclude from analysis")
parser.add_argument("--exclude_dst", nargs="+", default=[], help="Exclude these pointer destinations")
parser.add_argument("--save", dest='save', action='store_true', help="Save the filter bounds")
parser.add_argument("--print_offsets", action='store_true', help="print the offsets of the pointers")
parser.add_argument("--nohold", action='store_true', help="Don't hold out and just look at training set accuracy (sanity check, TPRs should be 1.0)")
args = parser.parse_args()

runnames = [f.split("_")[0] for f in os.listdir(args.dir) if f.endswith("maplist.pickle")]
rundata = []

for rn in runnames:
    rundata.append(RunContainer(rn, path=args.dir))

# Tally the most frequent pointers
pointer_dict = {}
for rd in rundata:
    pointer_dict = rd.rank_most_frequent(pointer_dict)

# Sort by frequency and extract the appropriate rank
pointerlist = [(ptr, pointer_dict[ptr]) for ptr in pointer_dict.keys()]
pointerlist.sort(key=lambda x: x[1], reverse=True)

# get the region and offset of the destination the user is interested in
ptr_region, ptr_offset = pointerlist[args.rank][0]

# 3D list containing all of the pointers to the target destination
# dimensions are run x heap_number x specific offset 
addrs = []
for rd in rundata:
    addrs.append(rd.scan_for_pointer(ptr_region, ptr_offset))

min_freq = min([sum([len(heap) for heap in run]) for run in addrs])

if min_freq == 0:
    exit("Pointer of rank {} not found in all runs. Try another pointer.".format(args.rank))

# smallest distance between any two pointers to the target destination
mindist = min([hp[i+1] - hp[i] 
                for run in addrs for hp in run 
                    for i in range(len(hp)-1)])

# calculate smallest alignment that fits all of the pointers
ref_ptr = min([a for hp in addrs[0] for a in hp]) # just take the smallest address from run 0 as a reference pointer
aln = args.pointer_sz
aln_offset = ref_ptr % aln

# Can we double the alignment and still keep all of the offsets the same?
while all([a% (2*aln) == ref_ptr % (2*aln) for run in addrs for hp in run for a in hp]) and 2*aln < mindist:
    aln = 2*aln
    aln_offset = ref_ptr % aln

# Create a pointer fingerprint 

lbs = np.zeros([len(rundata), args.preread + args.postread]) # lower bounds
ubs = np.zeros([len(rundata), args.preread + args.postread]) # upper bounds

for i,rd in enumerate(rundata):
    # flat list of all (heap_num, offset) tuples for run number i 
    addrs_agg = [(j,a) for (j,hp) in enumerate(addrs[i]) 
                            for a in hp if a >= args.preread and a < rd.get_heap_size(j) - args.postread]
    window_data = np.zeros([len(addrs_agg), args.preread + args.postread])
    for k, (heapnum, offset) in enumerate(addrs_agg):
        window_data[k] = np.array([b for b in rd.read_heap_bytes(heapnum, offset - args.preread, args.preread + args.postread)])
    
    lbs[i] = window_data.min(axis=0)
    ubs[i] = window_data.max(axis=0)


# Do leave-one-out cross validation

total_tru_list = [[len(hp) for hp in run] for run in addrs] # number of true pointers in each run and heap region
trupos_list = [[0 for hp in run] for run in addrs] # number of true positivies in each run and heap region
falsepos_list = [[0 for hp in run] for run in addrs] # number of false positives in each run and heap region
total_list = [[0 for hp in run] for run in addrs] # number of algined pointers in each run and heap region

for i,rd in enumerate(rundata):
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

    for heapnum, true_addrs in enumerate(addrs[i]):
        for offset, mem in rd.heap_iterator(heapnum, math.ceil(args.preread / aln)*aln, aln, args.preread, args.postread):
            mem = np.array(mem)
            total_list[i][heapnum] += 1
            
            if all(lb2 <= mem) and all(mem <= ub2): # memory matches the filter
                if offset in true_addrs:
                    trupos_list[i][heapnum] += 1
                else:
                    falsepos_list[i][heapnum] += 1

        print("HEAP {}: TPS: {}/{} FPS: {}/{}".format(heapnum, trupos_list[i][heapnum], 
                                                total_tru_list[i][heapnum], falsepos_list[i][heapnum],
                                                total_list[i][heapnum] - total_tru_list[i][heapnum]))
    
    print("TPS: {}/{} FPS: {}/{}".format(sum(trupos_list[i]), sum(total_tru_list[i]),
                                            sum(falsepos_list[i]), sum(total_list[i]) - sum(total_tru_list[i])))

# list recording precision
prec_list = [[t / (t + f) if t+f > 0 else 0 for t,f in zip(t_hp, f_hp)] for (t_hp, f_hp) in zip(trupos_list, falsepos_list)]

total_tps = sum([sum(run) for run in trupos_list])
total_fps = sum([sum(run) for run in falsepos_list])
total_tru = sum([sum(run) for run in total_tru_list])
total = sum([sum(run) for run in total_list])
total_false = total - total_tru

print("DESTINATION={}, OFFSET={}".format(ptr_region, ptr_offset))
print("POINTER ALIGNMENT={}".format(aln))
print("TOTAL TPR: {} ({}/{})".format(total_tps/total_tru, total_tps, total_tru))
print("TOTAL FPR: {} ({}/{})".format(total_fps/total_false, total_fps, total_false))
print("TOTAL PRECISION: {}".format(total_tps /(total_tps + total_fps)))
print("AVERAGE WORST-CASE PRECISION: {}".format(sum([min(run) for run in prec_list]) / len(prec_list)))