import pickle
import data_structures
import os
import sys

# Convert from old version to new version
def convert_maplist(f_old):
    ml = pickle.load(open(f_old, 'rb'))
    mlnew = data_structures.MapList()

    for start, end, name in ml:
        reg = data_structures.Region(start, end, "_".join(name.split("_")[:-1]))
        mlnew.add_region(reg)

    return mlnew

def convert_memgraph(f_old):
    mg = pickle.load(open(f_old, 'rb'))
    mgnew = data_structures.MemoryGraph(nodelist=[])
    mgnew.adj_matrix = mg

    return mgnew

def convert_dir(fdir):
    mls = [fdir + f for f in os.listdir(fdir) if f.endswith("maplist.pickle")]
    mgs = [fdir + f for f in os.listdir(fdir) if f.endswith("memgraph.pickle")]

    for f1, f2 in zip(mls, mgs):
        mlnew = convert_maplist(f1)
        mgnew = convert_memgraph(f2)

        pickle.dump(mlnew, open(f1,'wb'))
        pickle.dump(mgnew, open(f2,'wb'))

if __name__ == "__main__":
    convert_dir(sys.argv[1])