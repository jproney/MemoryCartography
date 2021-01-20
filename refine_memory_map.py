"""
Run memory cartograhy multiple times and bulid a refined memory graph
Example: python refine_memory_map.py 'gnome-terminal -- vim' --pgrepattach vim --num_repeats 3 --pgrepkill vim --outdir vim_map
Example Usage: python refine_memory_map.py 'firefox mozilla.org' --outdir ff_map --attach_time 15 --num_repeats 3 --pgrepattach 'Web Content' --pgrepkill 'firefox' --outidr ff_map
"""

import argparse
import os
import pickle
import datetime
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument("cmd", type=str, help="the command to run and analyze as it would normally be typed into a shell")
parser.add_argument("--outdir", type=str, default="memory_map_{}".format(datetime.datetime.now().strftime("%M%d%Y-%I%M")), help="directory to memory outputs")
parser.add_argument("--dump", dest='dump', action='store_true', help="Whether to actually run the program and dump the data. If not, will assume data is already present in outdir.")
parser.add_argument("--num_repeats",type=int, default=3, help="Re-run the binary")
parser.add_argument("--attach_time",type=int, default=0, help="How long (in seconds) to wait before attaching and analyzing. If 0, await user input")
parser.add_argument("--pgrepattach",type=str, default="", help="expression to pgrep for and attach to. If none is provided, will just attach to the PID of the spawned subprocess.")
parser.add_argument("--pgrepkill",type=str, default="", help="expression to pgrep when killing processes. If not specified, kills process found with pgrep")
parser.add_argument("--pointer_sz", type=int, default=8, help="Length of a pointer in memory being analyzed")


args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)
if args.dump:
    for i in range(args.num_repeats):
        child = subprocess.Popen(args.cmd.split(" "))
        if args.attach_time == 0:
            input("Press any key to pause and analyze memory...")
        else:
            time.sleep(args.attach_time)
        
        if len(args.pgrepattach) > 0:
            proc = subprocess.Popen(['pgrep', args.pgrepattach], stdout=subprocess.PIPE)
            pid = int(proc.stdout.read().decode().split("\n")[0])
        else:
            pid = child.pid

        # dump the memory
        os.system("sudo gdb -x cartography_gdb.py -ex 'py gdb_main({}, name=\"{}\", online=False, dump=True, psize={})'" \
            .format(
                pid, 
                "{}/run{}_".format(args.outdir, i), 
                args.pointer_sz))
        

        # determine who to kill
        if len(args.pgrepkill) > 0:
            os.system("pkill -9 '{}'".format(args.pgrepkill))    
        else:
            os.system("kill -9 {}".format(pid))    

    print("Finished dumping memory! Refining graph...")

#refine the memory graph
mg = None
for i in range(args.num_repeats):
    with open(args.outdir + "/run{}_".format(i) + "memgraph.pickle", "rb") as f:
        newmg = pickle.load(f)
        if mg:
            for src in mg.keys():
                for dst in mg[src].keys():
                    if (src not in newmg.keys()) or (dst not in newmg[src].keys()):
                        mg[src][dst] = []
                        continue

                    edgelist = mg[src][dst]
                    newmg_eset = set(newmg[src][dst])
                    newlist = []
                    for e in edgelist:
                        if e in newmg_eset:
                            newlist.append(e)
                    mg[src][dst] = newlist
        else:
            mg = newmg

# Add edges between regions with the same name that are always adjacent

maplists = [pickle.load(open(args.outdir + "/run{}_".format(i) + "maplist.pickle", "rb")) for i in range(args.num_repeats)]

mapdicts = [] # List of dictionaries, one for each run. Dictionaries simply map a region name to its start and end for more convenient retrieval.
for i in range(args.num_repeats):
    md = {}
    for reg in maplists[i]:
        md[reg[2]] = (reg[0], reg[1])
    mapdicts.append(md)


for src in mg.keys():
    if any([src not in md for md in mapdicts]):
        continue

    for dst in mg[src].keys():
        pref1 = "_".join(src.split("_")[:-1])
        pref2 = "_".join(dst.split("_")[:-1])
        if any([dst not in md for md in mapdicts]) or len(pref1) == 0 or len(pref2) == 0 or pref1 != pref2:
            continue

        if all([md[dst][1] == md[src][0] for md in mapdicts]) or all([md[dst][0] == md[src][1] for md in mapdicts]) :
            mg[src][dst].append((0,0)) # Virtual edge represents consistent spatial adjasency

with open(args.outdir + "/memgraph_final.pickle", "wb") as f:
    pickle.dump(mg, f)