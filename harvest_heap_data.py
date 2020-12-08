"""
Run the heap analysis code!
Example: python harvest_heap_data.py 'gnome-terminal -- vim' --pgrep vim
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
parser.add_argument("--heap_range",  type=str, default="0,0", help='Value like (2,10). If there are multiple regions with the specified name, we will analyze any' \
                                                'between 2 and 10 for example, following their order in /proc/./maps',)

parser.add_argument("--pgrepattach",type=str, default="", help="expression to pgrep for and attach to. If none is provided, will just attach to the PID of the spawned subprocess.")
parser.add_argument("--pgrepkill",type=str, default="", help="expression to pgrep when killing processes. If not specified, kills process found with pgrep")
parser.add_argument("--killsig",type=int, default=9, help="Signal number to send for killing processes. Defaults to KILL")

args = parser.parse_args()

os.makedirs(args.outdir, exist_ok=True)
for i in range(args.num_repeats):
    child = subprocess.Popen(args.cmd.split(" ") + ["&"])
    if args.attach_time == 0:
        input("Press any key to pause and analyze memory...")
    else:
        time.sleep(args.attach_time)
    
    if len(args.pgrepattach) > 0:
        proc = subprocess.Popen(['pgrep', args.pgrepattach], stdout=subprocess.PIPE)
        pid = int(proc.stdout.read().decode().split("\n")[0])
    else:
        pid = child.pid

    start, end = tuple(args.heap_range.split(','))

    strings = ['\"{}_{}\"'.format(args.heap_region, str(i)) for i in range(int(start), int(end)+1)]
    list_string = '[' + ','.join(strings) + ']'

    print(list_string)

    # dump the memory
    os.system("sudo gdb -x cartography_gdb.py -ex 'py gdb_main({}, {}, True, \"{}\")'".format(pid, list_string, args.outdir + "/run{}_".format(i)))
    
    # determine who to kill
    if len(args.pgrepkill) > 0:
        os.system("pkill -{} '{}'".format(args.killsig, args.pgrepkill))    
    else:
        os.system("kill -{} {}".format(args.killsig, pid))    