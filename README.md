# Code from the Paper "Identifying Valuable Pointers in Heap Data" from WOOT 2021

## [Paper Link]([https://mickens.seas.harvard.edu/files/mickens/files/memory_cartography.pdf](https://ieeexplore.ieee.org/document/9474326)) 

## Overview

This repository contains tools for performing memory cartography attacks and discovering pointers to data sections inside unstructured heap data.

Tested and working with the following environment(s):

* Python 3.8.5
* GDB 9.2
* Ubuntu 20.04, Ubuntu 18.04, Ubuntu 12.04

Python Dependencies:

* numpy
* selenium (for simulating realistic web server traffic, not required for memory analysis)


## Steps to reproduce results from the paper:

1. Vim

To reproduce the results of the paper on the Vim text editor (tested on Vim 8.1.2269), run:

```
python harvest_heap_data.py 'gnome-terminal -- vim' --pgrepattach vim --num_repeats 10 --pgrepkill vim --outdir vim_heap_analysis
```

This will open a terminal with the Vim editor launched. Do whatever you want in the editor window, and then press any key on the 
original terminal to begin harvesting the data. This cycle will repeat 10 times.

Now to analyze the results of the memory dumps run:

```
python analyze.py vim_heap_analysis/ --rank 0
```

Substitute other numbers into the "rank" field to explore other discovered pointers.

To build the memory cartography graph on Vim run:

```
python refine_memory_map.py 'gnome-terminal -- vim' --pgrepattach vim --num_repeats 3 --pgrepkill vim --outdir vim_map --dump
```

To determine the number of regions reachable from the region vim.basic_4, run

```
python graph_util.py vim_map/memgraph_final.json --region /usr/bin/vim.basic_4
```

Note: An unpleasant sideaffect is the abundance of `.sw*` files produced. Do `rm .sw*` to get rid of these once you're done.

2. Firefox

To reproduce the results on Firefox (tested on Firefox 87.0), run:

```
python harvest_heap_data.py 'firefox mozilla.org' --outdir ff_heap --attach_time 15 --num_repeats 10 --pgrepattach 'Web Content' --pgrepkill 'firefox' --heap_region '' --length_lb 1048576 --length_ub 1048576
```

then to analyze

```
python analyze.py ff_heap/ --rank 0
```

To build the memory cartography map on firefox run:

```
python refine_memory_map.py 'firefox mozilla.org' --outdir ff_map --attach_time 15 --num_repeats 3 --pgrepattach 'Web Content' --pgrepkill 'firefox' --dump
```

To determine the connectivity of `libxul.so.2` run:

```
python graph_util.py ff_map/memgraph_final.json --region /usr/lib/firefox/libxul.so_2
```

3. Apache + Heartbleed

For our attack on Apache, we used an Ubuntu 12.04 VM with OpenSSL 1.0.1, which is vulnerable to Heartbleed. Our VM image was based off of the image found [here](http://pages.cs.wisc.edu/~rist/642-spring-2014/hw/hwEC.html) (credit to Thomas Ristenpart). 

To log into the VM image, select the account called "heartbleed" and enter the password "heartbleed."

Alternatively, you can start the VM in headless mode, and log in by executing `ssh -A user@192.168.26.3` and entering the password "heartbleed."

First, get the Apache server running on the Heartbleed VM. (Make sure to do `sudo /etc/init.d/nginx stop` and `sudo /etc/init.d/apache2 restart`)

If the server is running, you should be able to access a simple wordpress site at `192.168.26.3:443`. To make sure that heartbleed is working, try running `nmap -p 443 --script sll-heartbleed 192.168.26.3` from the host machine.


Heartbleed leaks from a specific labelled heap in single-process Apache (`[heap]_1`).  To run memory cartography, execute the following from `/home/user/Documents/MemoryCartography` in the VM:

```
python3 harvest_heap_data.py 'sudo /etc/init.d/apache2 stop; sleep 2; sudo /etc/init.d/apache2 start; echo "done!"' --outdir apache_heap --attach_time 0 --num_repeats 10 --pgrepattach 'apache' --pgrepuser 'www-data' --pgrepkill 'apache' --killsig 0 --nograph
```

After the server starts, run `python wordpress.py` from the host machine to activate the stress test. After the stress test finished running, press any key in the VM terminal to trigger memory analysis. This cycle will repeat 10 times.

Copy the memory dumps from the VM to the host:

```
scp -r user@192.168.26.3:/home/user/Documents/MemoryCartography/apache_heap ./
```

Next, build the memory graphs offline:

```
python build_graph.py apache_heap/ --n 10 --pointer_sz 4
```

And analyze:

```
python analyze.py apache_heap/ --rank 0 --heapnames [heap]_1 --pointer_sz 4
```

Back on the VM, run the following to build the full memory graph. Like before, running "python wordpress.py" on the host once each iteration.

```
python3 refine_memory_map.py 'sudo /etc/init.d/apache2 stop; sleep 2; sudo /etc/init.d/apache2 start; echo "done!"' --outdir apache_map --attach_time 0 --num_repeats 3 --pgrepattach 'apache' --pgrepuser 'www-data' --pgrepkill 'apache' --killsig 0 --dump --nograph
```

Copy again:

```
scp -r user@192.168.26.3:/home/user/Documents/MemoryCartography/apache_map ./
```

Build the graph:

```
python build_graph.py apache_map/ --n 3 --pointer_sz 4
python3 refine_memory_map.py '' --outdir apache_map --num_repeats 3
```

And analyze connectivity:

```
python graph_util.py apache_map/memgraph_final.json --region /usr/lib/apache2/modules/libphp5.so_0
```

## Published Data

Instead of running the experiments on your own system, you can also download the results of our experiments in the form of memory dumps and data structures. After downloading the data, you can perform the analysis yourself to reproduce the results from the paper.

The data from our experiments on Vim, Firefox, and Apache, as well as our HeartBleed VM image, are available [here](https://drive.google.com/drive/u/1/folders/1Fmi7DAaCydWX8G2kt87Zedw5Q8aQQn1h).

To use, simply download, extract the archive, and run the analysis scripts as detailed in the previous section.

Exapmle with the Vim heap:

```
tar -xf vim_heap.tar.gz 
python analyze.py vim_heap/ --rank 0
```

Example with Vim memory map:

```
tar -xf vim_map.tar.gz
python graph_util.py vim_map/memgraph_final.json --region /usr/bin/vim.basic_4
```
