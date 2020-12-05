"""
Run the heap analysis code!
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
parser.add_argument("--num_repeats",type=int, default=5, help="Re-run the binary")
parser.add_argument("--heap_region",type=str, default="[heap]", help="name of the memory region to analyze (as seen in proc/pid/maps)")
parser.add_argument("--attach_time",type=int, default=0, help="How long (in seconds) to wait before attaching and analyzing. If 0, await user input")
parser.add_argument("--region_number",type=int, default=0, help="If there are multiple regions with the specfied name, this index specifies which one to use \
                                                                (based on the order of the regions in /proc/pid/maps)")
parser.add_argument("--pgrep",type=str, default="", help="expression to pgrep for and attach to. If none is provided, will just attach to the PID of the spawned subprocess.")
args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)
for i in range(args.num_repeats):
    child = subprocess.Popen(args.cmd.split(" ") + ["&"])
    if args.attach_time == 0:
        input("Press any key to pause and analyze memory...")
    else:
        time.sleep(args.attach_time)
    
    if len(args.pgrep) > 0:
        proc = subprocess.Popen(['pgrep', args.pgrep], stdout=subprocess.PIPE)
        pid = int(proc.stdout.read().decode().split("\n")[0])
    else:
        pid = child.pid

    # dump the memory
    os.system("sudo gdb -x cartography_gdb.py -ex 'py gdb_main({}, [\"{}_{}\"], True, \"{}\")'".format(pid, args.heap_region, args.region_number, args.outdir + "/run{}_".format(i)))
    os.system("kill -9 {}".format(pid))