"""
Run memory cartograhy multiple times and bulid a refined memory graph
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
parser.add_argument("--num_repeats",type=int, default=3, help="Re-run the binary")
parser.add_argument("--attach_time",type=int, default=0, help="How long (in seconds) to wait before attaching and analyzing. If 0, await user input")
parser.add_argument("--pgrepattach",type=str, default="", help="expression to pgrep for and attach to. If none is provided, will just attach to the PID of the spawned subprocess.")
parser.add_argument("--pgrepkill",type=str, default="", help="expression to pgrep when killing processes. If not specified, kills process found with pgrep")

args = parser.parse_args()

mg = None
os.makedirs(args.outdir, exist_ok=True)
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
    os.system("sudo gdb -x cartography_gdb.py -ex 'py gdb_main({}, dump=True, name=\"{}\", online=False)'" \
        .format(
            pid, 
            "{}/run{}_".format(args.outdir, i), 
            ))
    

    # determine who to kill
    if len(args.pgrepkill) > 0:
        os.system("pkill -9 '{}'".format(args.pgrepkill))    
    else:
        os.system("kill -9 {}".format(pid))    
    #refine the memory graph
    with open(args.outdir + "/run{}_".format(i) + "memgraph.pickle", "rb") as f:
        newmg = pickle.load(f)
        if mg:
            for src in mg.keys():
                for dst in mg[src].keys():
                    edgelist = mg[src][dst]
                    newlist = []
                    for e in edgelist:
                        if e in newmg[src][dst]:
                            newlist.append(e)
                    mg[src][dst] = newlist
        else:
            mg = newmg

with open(args.outdir + "/memgraph_final.pickle", "wb") as f:
    pickle.dump(mg, f)