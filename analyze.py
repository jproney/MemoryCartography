import pickle
import struct 
import numpy as np

heapname = "[heap]_0"

maplist = pickle.load(open("maplist.pickle",'rb'))
mgraph = pickle.load(open("memgraph.pickle",'rb'))
heap = open(heapname + ".dump",'rb')

mapdict = {}
for reg in maplist:
    mapdict[reg[2]] = (reg[0], reg[1])

def read_heap_bytes(offset, nbytes):
    heap.seek(offset)
    return heap.read(nbytes)

def read_heap_pointer(offset):
    heap.seek(offset)
    return struct.unpack('P', heap.read(8))[0]

def read_heap_int(offset):
    heap.seek(offset)
    return struct.unpack('<i', heap.read(4))


# Get statistics about which pointer destinations are most frequent

pointerdict = {}
for dst in mgraph[heapname].keys():
    for ptr in mgraph[heapname][dst]:
        if (dst, ptr[1]) in pointerdict:
            pointerdict[(dst, ptr[1])] += 1
        else:
            pointerdict[(dst, ptr[1])] = 1
        
pointerlist = sorted(pointerdict.items(), key=lambda item: item[1], reverse=True)

# Starting with the most frequent, look for "fingerprints" surrounding the pointers

section, offset = pointerlist[0][0]
addrs = sorted([mapdict[heapname][0] + edge[0] for edge in mgraph[heapname][section] if edge[1] == offset])

# Find the minimum distance between any two pointers of interest 
mindist = min([addrs[i + 1] - addrs[i] for i in range(0, len(addrs)-1)])

# Assume pointers live in a struct and determine its alignment
aln = 8
while all([a%(aln*2) == addrs[0]%(aln*2) for a in addrs]) and aln < mindist:
    aln *= 2

# Read two alignment's-worth of data behind and in front of the aligned pointer address (heuristic choice)
preread = 2
postread = 2

prints = np.zeros([len(addrs), 4*aln])
for i,a in enumerate(addrs):
    base = (a//aln) * aln
    prints[i,:]  = np.array([x for x in read_heap_bytes(base - mapdict[heapname][0] - preread*aln, (preread + postread)*aln)])

# Record a range of observed values for each byte in the observed range
lbs = prints.min(axis=0)
ubs = prints.max(axis=0)

# Test the accuracy of pointer fingerprinting on the test data
trupos = []
falsepos = []
for offset in range(preread*aln, mapdict[heapname][1] - mapdict[heapname][0] - postread*aln, aln):
    dat = np.array([x for x in read_heap_bytes(offset - preread*aln, (preread + postread)*aln)])
    if all(lbs <= dat) and all(dat <= ubs):
        if mapdict[heapname][0] + offset in addrs:
            trupos.append(offset)
        else:
            falsepos.append(offset)

print("TPR: {}".format(len(trupos)/len(addrs)))
print("FPR: {}".format(len(falsepos)/((mapdict[heapname][1] - mapdict[heapname][0])//aln - len(addrs))))