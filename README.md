# Final Project on Memory Cartography

To run memory cartography on the monsters example, do something like this:
```python3 harvest_heap_data.py 'firefox file:///~/MemoryCartography/monsters_example.html' --outdir firefox_out_monsters --attach_time 10 --num_repeats 5 --pgrepattach 'file' --pgrepkill 'firefox' --heap_region '' --heap_range 1,1 --offline --orderby 1```

To analyze this, do something like:
```python3 analyze.py firefox_out_monster\ --heap_idx 1 --rank 0```