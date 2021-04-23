"""
Generate raw data from figure 2 in the paper
"""

from data_structures import RunContainer
import os

heap_dir = "ff_heap/"
runnames = sorted([f.split("_")[0] for f in os.listdir(heap_dir) if f.endswith("maplist.json")])
rundata = []

for rn in runnames:
    rundata.append(RunContainer(rn, path=heap_dir))

# Tally the most frequent pointers
pointer_dict = {}
for rd in rundata:
    pointer_dict = rd.rank_most_frequent(pointer_dict)

# Sort by frequency and extract the appropriate rank
pointerlist = [(ptr, pointer_dict[ptr]) for ptr in pointer_dict.keys()]
pointerlist.sort(key=lambda x: x[1], reverse=True)

# get the region and offset of the destination the user is interested in
ptr_region, ptr_offset = pointerlist[0][0]
print(ptr_region)
print(ptr_offset)

with open("fig2.csv","w") as f:
    for rd in rundata:
        counts = [len(x) for x in rd.scan_for_pointer(ptr_region, ptr_offset)]
        f.write(",".join([str(c) for c in sorted(counts)]) + "\n")


