"""
Run memory cartograhy multiple times and bulid a refined memory graph
Example: python refine_memory_map.py 'gnome-terminal -- vim' --pgrepattach vim --num_repeats 3 --pgrepkill vim --outdir vim_map --dump
Example Usage: python refine_memory_map.py 'firefox mozilla.org' --outdir ff_map --attach_time 15 --num_repeats 3 --pgrepattach 'Web Content' --pgrepkill 'firefox' --outidr ff_map --dump
"""

import data_structures
import argparse
import os
import datetime
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument("cmd", type=str, help="the command to run and analyze as it would normally be typed into a shell")
parser.add_argument("--outdir", type=str, default="memory_map_{}".format(datetime.datetime.now().strftime("%M%d%Y-%I%M")), help="directory to memory outputs")
parser.add_argument("--dump", dest='dump', action='store_true', help="Whether to actually run the program and dump the data. If not, will assume data is already present in outdir.")
parser.add_argument("--num_repeats",type=int, default=3, help="Re-run the binary")
parser.add_argument("--attach_time",type=int, default=0, help="How long (in seconds) to wait before attaching and analyzing. If 0, await user input")
parser.add_argument("--pgrepuser",type=str, default="", help="owner of the sought process (ie, www-data for apache handlers)")
parser.add_argument("--pgrepattach",type=str, default="", help="expression to pgrep for and attach to. If none is provided, will just attach to the PID of the spawned subprocess.")
parser.add_argument("--pgrepkill",type=str, default="", help="expression to pgrep when killing processes. If not specified, kills process found with pgrep")
parser.add_argument("--pointer_sz", type=int, default=8, help="Length of a pointer in memory being analyzed")
parser.add_argument("--nograph", dest='nograph', action='store_true', help="Don't build out the graph. Just save the maplists and dumps and build the graph later")
parser.add_argument("--killsig",type=int, default=9, help="Signal number to send for killing processes. Defaults to KILL")
parser.add_argument("--coalesce", dest='coalesce', action='store_true', help="combine adjacent same-named memory regions")

args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)
if args.dump:
    for i in range(args.num_repeats):
        print("Launching...")
        child = subprocess.Popen(args.cmd, shell=True)
        if args.attach_time == 0:
            input("Press any key to pause and analyze memory...")
        else:
            print("Pausing for {} seconds".format(args.attach_time))
            time.sleep(args.attach_time)

        if len(args.pgrepattach) > 0:
            if len(args.pgrepuser) > 0:
                proc = subprocess.Popen(['pgrep', '-u', args.pgrepuser, args.pgrepattach], stdout=subprocess.PIPE)
            else:
                proc = subprocess.Popen(['pgrep', args.pgrepattach], stdout=subprocess.PIPE)
            pid = int(proc.stdout.read().decode().split("\n")[0])
        else:
            pid = child.pid

        # dump the memory
        os.system("sudo gdb -x cartography_gdb.py -ex 'py gdb_main({}, name=\"{}\", psize={}, graph={}, coalesce={})'" \
            .format(
                pid, 
                "{}/run{}_".format(args.outdir, i), 
                args.pointer_sz,
                not args.nograph,
                args.coalesce))
        

        # determine who to kill
        if len(args.pgrepkill) > 0:
            os.system("pkill -{} '{}'".format(args.killsig, args.pgrepkill))    
        else:
            os.system("kill -{} {}".format(args.killsig, pid))  

    print("Finished dumping memory! Refining graph...")

if not args.nograph:

    #refine the memory graph
    mg = None
    for i in range(args.num_repeats):
        newmg = data_structures.MemoryGraph()
        newmg.deserialize(args.outdir + "/run{}_".format(i) + "memgraph.json")
        if mg:
            for src in mg.adj_matrix.keys():
                for dst in mg.adj_matrix[src].keys():
                    if (src not in newmg.adj_matrix.keys()) or (dst not in newmg.adj_matrix[src].keys()):
                        mg.adj_matrix[src][dst] = [] # remove inconcsistent edges
                        continue

                    edgelist = mg.adj_matrix[src][dst]
                    newmg_eset = set(newmg.adj_matrix[src][dst])
                    newlist = []
                    for e in edgelist:
                        if e in newmg_eset:
                            newlist.append(e)
                    mg.adj_matrix[src][dst] = newlist
            else:
                mg = newmg

    mg.serialize(args.outdir + "/memgraph_final.json")