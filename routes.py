import os
import csv
import math
import networkx as nx 


def open_tables(nodes, edges):
    # 1. nodes.csv -> Dictionary{label:[x,y]}
    with open(nodes, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                nodedict = {}
                line_count += 1
            print(row["label"])
            nodedict[row["label"]] = {"x": row["x"], "y": row["y"]}
            line_count += 1
        print(f'Processed {line_count} lines.')
        print(nodedict)

    # 2. edges.csv -> List[(node1, node2)]
    with open(edges, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                edgelist = []
                line_count += 1
            edgelist.append((row["node1"], row["node2"]))
            line_count += 1
        print(f'Processed {line_count} lines.')
        print(edgelist)

    # 3. next, create the graph
    mDG = nx.MultiDiGraph()
    for i in nodedict:
        mDG.add_nodes_from([
            (i, {"x": nodedict[i]["x"], "y": nodedict[i]["y"]}),
        ])
    mDG.add_edges_from(edgelist)
    print(mDG)

    return mDG, nodedict


def create_table(multiDiGraph, nodedict, finalpath):
    # 1. get all paths + their lengths
    pathlengths = []
    mappingdict = {}
    edgelengths = {}
    for path in nx.all_simple_edge_paths(multiDiGraph, "Source", "Target"):
        lengthofpath = 0
        for i in path:
            print(path)
            if i in edgelengths:
                lengthofpath = lengthofpath + edgelengths[i]
            else:
                firstnode = i[0]
                secondnode = i[1]
                x = int(nodedict[secondnode]["x"]) - int(nodedict[firstnode]["x"])
                y = int(nodedict[secondnode]["y"]) - int(nodedict[firstnode]["y"])
                lengthofedge = math.hypot(x, y)
                edgelengths[i] = lengthofedge
                lengthofpath = lengthofpath + lengthofedge
        mappingdict[lengthofpath] = path
        pathlengths.append(lengthofpath)
    
    # 2. the data needs to get prepared
    pathlengths.sort(reverse=True)
    final = []
    for i in pathlengths:
        pair = [i, mappingdict[i]]
        final.append(pair)

    # 3. now the .csv file needs to be filled
    with open(finalpath, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["length", "route"])
        writer.writerows(final)


def calculate(nodefile, edgefile, finalpath):
    name1, extension1 = os.path.splitext(nodefile)
    name2, extension2 = os.path.splitext(edgefile)
    if extension1 == ".csv" and extension2 == ".csv":
        multiDiGraph, nodedict = open_tables(nodefile, edgefile)
        create_table(multiDiGraph, nodedict, finalpath)
    else:
        print("Wrong file type")
