"""
Tests a generated classifier against a glob of binaries
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
import glob

pointer_sz = struct.calcsize("P")

parser = argparse.ArgumentParser()
parser.add_argument("dir", help="output directory with binaries and memlists, labeled like [num]_binary.bin and [num]_memlists.pickle")
parser.add_argument("classifier", help="classifier to analyze")
args = parser.parse_args()

# list of memory lists
listfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith("memgraph.pickle")])
memlists = [pickle.load(open(gf, "rb")) for gf in graphfiles]

binfiles = sorted([args.dir + f for f in os.listdir(args.dir) if f.endswith("binary.bin")])
bins = [(bf, open(bf, "rb")) for bf in binfiles]

# lb_final, ub_final, section, dst_offset, aln, aln_offset
classifier = pickle.load(open(args.classifier, "rb"))
aln = classifier[4]
aln_offset = classifier[5]
preread = aln*2
postread = aln*2

# Utility functions for reading things from the heap dumps
def read_heap_bytes(heapfile, offset, nbytes):
    heapfile.seek(offset)
    return heapfile.read(nbytes)

def read_heap_pointer(heapfile, offset):
    heapfile.seek(offset)
    return struct.unpack('P', heapfile.read(pointer_sz))[0]

def read_heap_int(heapfile, offset):
    heapfile.seek(offset)
    return struct.unpack('<i', heapfile.read(4))


for i, (bf_name, bf)  in enumerate(bins):
  memlist = memlists[i]

  # tp and fp statistics for this held-out heap
  current_tps = 0
  current_fps = 0

  total_checked = 0

  file_len = os.path.getsize(bf_name)

  for offset in range(math.ceil(preread/aln)*aln + aln_offset, file_len - postread, aln):

    # What does the filter say?
    dat = np.array([x for x in read_heap_bytes(bf, offset - preread, (preread + postread))]) #read data from the heap
    
    # hit
    if all(classifier[0] <= dat) and all(dat <= classifier[1]):

      # Is this a real pointer?
      val = read_heap_pointer(bf, offset)

      if any([l_name == classifier[2] and dst_offset == val - l_start for l_start, l_end, l_name in memlist]):
        current_tps += 1
      else:
        current_fps += 1

    total_checked += 1

  print("BIN {}: TPS: {}/{} FPS: {}/{}".format(bf_name, current_tps, total_checked, current_fps, total_checked))
