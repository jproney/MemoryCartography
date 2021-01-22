# Final Project on Memory Cartography

This repository contains tools for performing memory cartography attacks and discovering pointers to 
data sections inside unstructured heap data.


Steps to reproduce results from the paper.

1. Vim

To reproduce the results of the paper on the Vim text editor, run:

python harvest_heap_data.py 'gnome-terminal -- vim' --pgrepattach vim --num_repeats 10 --pgrepkill vim --outdir vim_heap_analysis

This will open a terminal with the Vim editor launched. Do whatever you want in the editor window, and then press any key on the 
original terminal to begin harvesting the data. This cycle will repeat 10 times.

Now to analyze the results of the memory dumps run:

python analyze.py vim_heap_analysis/ --rank 0

To build the memory cartography graph on Vim run:

python refine_memory_map.py 'gnome-terminal -- vim' --pgrepattach vim --num_repeats 3 --pgrepkill vim --outdir vim_map --dump

To determine the number of regions reachable from the region vim.basic_4, run

python graph_util.py vim_map/memgraph_final.pickle --region /usr/bin/vim.basic_4

Note: An unpleasant sideaffect is the abundance of .sw* files produced. Do rm .sw* to get rid of these once you're done.

2. Firefox

To reproduce the results on Firefox, run:

python harvest_heap_data.py 'firefox mozilla.org' --outdir ff_heap --attach_time 15 --num_repeats 10 --pgrepattach 'Web Content' --pgrepkill 'firefox' --heap_region '' --length_lb 1048576 --length_ub 1048576

then to analyze

python analyze.py ff_heap/ --rank 0

To build the memory cartography map on firefox run:

python refine_memory_map.py 'firefox mozilla.org' --outdir ff_map --attach_time 15 --num_repeats 3 --pgrepattach 'Web Content' --pgrepkill 'firefox' --dump

To determine the connectivity of libxul.so.2 run:

python graph_util.py ff_map/memgraph_final.pickle --region /usr/lib/firefox/libxul.so_2

3. Apache + Heartbleed

First, get the Apache wordpress server running on the Heartbleed VM. (Make sure to do /etc/init.d/nginx stop)

Heartbleed leaks from labelled heap in single-process Apache ([heap]_1).  To run memory cartography, executing the following from /home/user/Documents/MemoryCartography in the VM:

python3 harvest_heap_data.py 'sudo /etc/init.d/apache2 stop; sleep 2; sudo /etc/init.d/apache2 start; echo "done!"' --outdir apache_heap --attach_time 0 --num_repeats 10 --pgrepattach 'apache' --pgrepuser 'www-data' --pgrepkill 'apache' --killsig 0 --nograph

During each round of memory analysis, run "python wordpress.py" from the host machine to activate the stress test.

Copy the memory dumps from the VM to the host:

scp -r user@192.168.26.3:/home/user/Documents/MemoryCartography/apache_heap ./

Next, build the memory graphs offline:

python offline_graph.py apache_heap/ --n 10 --pointer_sz 4

And analyze:

python analyze.py apache_heap/ --rank 0 --exclude_src [heap]_2 [heap]_0 --pointer_sz 4

Back on the VM, run the following to build the full memory graph. Like before, running "python wordpress.py" on the host once each iteration.

python3 refine_memory_map.py 'sudo /etc/init.d/apache2 stop; sleep 2; sudo /etc/init.d/apache2 start; echo "done!"' --outdir apache_map --attach_time 0 --num_repeats 3 --pgrepattach 'apache' --pgrepuser 'www-data' --pgrepkill 'apache' --killsig 0 --dump --nograph

Copy again:

scp -r user@192.168.26.3:/home/user/Documents/MemoryCartography/apache_map ./

Build the graph:

python offline_graph.py apache_map/ --n 3 --pointer_sz 4

python3 refine_memory_map.py '' --outdir apache_map --num_repeats 3

And analyze connectivity:

python graph_util.py apache_map/memgraph_final.pickle --region /usr/lib/apache2/modules/libphp5.so_0
