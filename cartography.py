"""
Map out allocated memory regions in a specificed binary.
Example usage:
gdb -x cartography.py -ex 'py build_map("tests/harvest_pointers.out", 16, [])'
"""

import gdb #won't work unless script is being run under a GDB process
import argparse
import subprocess
import re


def build_map(executable, break_line, program_args):
    gdb.execute("file " + executable + " " + " ".join(program_args))
    gdb.execute("break " + str(break_line))
    gdb.execute("run")

    # At breakpoint. Get the addresses of all of the mapped memory regions
    maps = [re.split(r'\s{1,}', s)[1:] for s in gdb.execute("info proc mappings", False, True).split("\n")[4:-1]]
    mapdict={}
    for segment in maps:
        segname = segment[-1]
        if segname in ["[vvar]", "[vdso]", "[vsyscall]",""]: #ignore these regions
            continue
        if segname not in mapdict:
            mapdict[segname] = [(int(segment[0],16), int(segment[1],16))]
        else:
            if int(segment[0], 16) == mapdict[segname][-1][1]: #comibine adjascent memory ranges into one range
                mapdict[segname][-1] = (mapdict[segname][-1][0], int(segment[1], 16))
            else:
                mapdict[segname].append((int(segment[0],16), int(segment[1],16)))
        
    print(mapdict)
    
    def check_pointer(val):
        #is val a pointer to any of our mapped regions?
        for seg in mapdict.keys():
            for i,reg in enumerate(mapdict[seg]):
                if reg[0] <= val and val < reg[1]:
                    return seg, i, val-reg[0]
        return None

    memgraph = {} #edge list
    
    for segname in mapdict.keys():
        for i,region in enumerate(mapdict[segname]):
            for addr in range(region[0], region[1]-7):
                val = int(gdb.execute("x/g " + str(addr), False, True).split()[-1])
                dst = check_pointer(val)
                if dst:
                    dstseg, dstreg, offset = dst
                    regname = segname + "_" + str(i)
                    if regname not in memgraph:
                        memgraph[regname] = []
                    memgraph[regname].append((regname, addr-region[0], dstseg + "_" + str(dstreg), offset)) 

    print(memgraph[maps[0][-1] + "_0"])