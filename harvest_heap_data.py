"""
Run the heap analysis code!
Example: python harvest_heap_data.py 'gnome-terminal -- vim' --pgrepattach vim --num_repeats 10 --pgrepkill vim --outdir vim_heap_analysis
Example: python harvest_heap_data.py 'firefox mozilla.org' --outdir ff_heap --attach_time 15 --num_repeats 10 --pgrepattach 'Web Content' --pgrepkill 'firefox' --heap_region '' --length_lb 1048576 --length_ub 1048576
See parser for input arguments. Reuslt files will be saved to "outdir," and can then be analyzed using `analyze.py`
"""

import argparse
import os
import pickle
import datetime
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument("cmd", type=str, help="the command to run and analyze as it would normally be typed into a shell")
parser.add_argument("--outdir", type=str, default="heap_analysis_{}".format(datetime.datetime.now().strftime("%M%d%Y-%I%M")), help="directory to dump outputs")
parser.add_argument("--num_repeats",type=int, default=10, help="times to re-run the binary")

parser.add_argument("--heap_region",type=str, default="[heap]", help="name of the memory region to analyze (as seen in proc/pid/maps)")
parser.add_argument("--attach_time",type=int, default=0, help="How long (in seconds) to wait before attaching and analyzing. If 0, await user input")
parser.add_argument("--length_lb",type=int, default=-1, help="lower bound on the length of scanned regions")
parser.add_argument("--length_ub",type=int, default=2**32, help="upper bound on the length of scanned regions")

parser.add_argument("--pgrepattach",type=str, default="", help="expression to pgrep for and attach to. If none is provided, will just attach to the PID of the spawned subprocess.")
parser.add_argument("--pgrepuser",type=str, default="", help="owner of the sought process (ie, www-data for apache handlers)")
parser.add_argument("--pgrepkill",type=str, default="", help="expression to pgrep when killing processes. If not specified, kills process found with pgrep")
parser.add_argument("--killsig",type=int, default=9, help="Signal number to send for killing processes. Defaults to KILL")

parser.add_argument("--nograph", dest='nograph', action='store_true', help="Don't build out the graph. Just save the maplists and dumps and build the graph later")

parser.add_argument("--coalesce", dest='coalesce', action='store_true', help="combine adjacent same-named memory regions")
parser.add_argument("--pointer_sz", type=int, default=8, help="Length of a pointer in memory being analyzed")


args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)
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


    list_string = '["{}"]'.format(args.heap_region)

    # call into the gdb script to map the VMAs and scann for pointers
    os.system("sudo gdb -x cartography_gdb.py -ex 'py gdb_main({}, sources={}, name=\"{}\", llb={}, lub={}, graph={}, psize={}, coalesce={})'" \
        .format(
            pid, 
            list_string, 
            "{}/run{}_".format(args.outdir, i), 
            args.length_lb,
            args.length_ub,
            not args.nograph,
            args.pointer_sz,
            args.coalesce))
    
    # determine who to kill
    if len(args.pgrepkill) > 0:
        os.system("pkill -{} '{}'".format(args.killsig, args.pgrepkill))    
    else:
        os.system("kill -{} {}".format(args.killsig, pid))  
    time.sleep(3)  