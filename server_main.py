from flask import Flask, jsonify
import numpy as np
import configparser
from scripts.algorithm import *
from os import getcwd, makedirs, listdir

import json
from os.path import join, exists
import math
from os import getcwd
from os.path import join
from warehouse import WareHouse

import gc

from scripts.clustering import performClustering

SERVER_ROOT = getcwd()
warehouse = None

app = Flask(__name__, static_url_path="/static")

POSTERIOR_SPLIT_SIZE = 10
from flask import request

TREE_ALL_DATA = {}

def init_warehouse(dataset):
    global warehouse
    warehouse = WareHouse(dataset, join(SERVER_ROOT, "result", dataset))

@app.route('/api/confusion-matrix', methods=['GET'])
def get_confusion_matrix():
    dataset_identifier = request.args["dataset"]
    setname = request.args["setname"]
    dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
    confusion_matrix = np.load(join(dataset_path, "confusion_matrix_" + setname + ".npy"))
    return jsonify(confusion_matrix.tolist())

# add by Shouxing, 2017 / 7 / 20
@app.route('/api/feature_matrix_for_cluster', methods=['GET'])
def get_feature_matrix_for_cluster():
    cluster_ids = json.loads(request.args.get('cluster_ids'))
    cluster_classes = json.loads(request.args.get('cluster_classes'))
    features = json.loads(request.args.get('features'))
    # TODO get matrix of instances and features: feature_raw
    feature_raw = np.array([[0]])
    size = len(cluster_ids)
    # TODO get the directory path
    features_split_values = np.load('features_split_values.npy')
    features_split_widths = np.load('features_split_widths.npy')

    feature_matrix = []
    for feature_id in features:
        row = []
        for i in range(size):
            instance_ids = []  # get by cluster_ids[i] and cluster_classes[i]
            # TODO get instance ids for a tuple (cluster_id, cluster_class):
            bins = features_split_values[feature_id]
            feature_values = [feature_raw[instance_id][feature_id] for instance_id in instance_ids]
            distribution = get_feature_distribution(feature_values, bins)
            row.append(distribution)
        feature_matrix.append(row)
    return jsonify({
        'feature_matrix': feature_matrix,
        'feature_widths': features_split_widths.tolist()
    })

# add by Shouxing, 2017 / 7 / 20
@app.route('/api/feature_matrix_for_class', methods=['GET'])
def get_feature_matrix_for_class():
    dataset_identifier = request.args["dataset"]
    setname = request.args["setname"]
    class_id = json.loads(request.args['class_id'])
    features = json.loads(request.args['features'])
    # features = [int(f) for f in features.split("-")]
    global warehouse
    print(warehouse)

    dataset_path = join(SERVER_ROOT, "result", dataset_identifier)
    feature_raw = np.load(join(dataset_path, "feature-raw-" + setname + ".npy"))
    instance_labels = np.load(join(dataset_path, "label-" + setname + ".npy"))
    features_split_values = np.load(join(SERVER_ROOT, "result", dataset_identifier, "features_split_values.npy"))
    features_split_widths = np.load(join(SERVER_ROOT, "result", dataset_identifier, "features_split_widths.npy"))
    size = len(instance_labels)
    class_instance_ids = [[],[]]
    for i in range(size):
        if instance_labels[i] == class_id:
            class_instance_ids[0].append(i)
        else:
            class_instance_ids[1].append(i)

    feature_matrix = []
    for feature_id in features:
        row = []
        for i in range(2):
            instance_ids = class_instance_ids[i]
            bins = features_split_values[feature_id]
            feature_values = [feature_raw[instance_id][feature_id] for instance_id in instance_ids]
            distribution = get_feature_distribution(feature_values, bins)
            row.append(distribution)
        feature_matrix.append(row)
    return jsonify({
        'feature_matrix': feature_matrix,
        'feature_widths': features_split_widths.tolist()
    })

# add by Shouxing, 2017 / 7 / 20
@app.route('/api/bin_exist_for_instance', methods=['GET'])
def get_bin_exist_for_instance():
    instance_id = json.loads(request.args.get('instance_id'))
    features = json.loads(request.args.get('features'))
    # TODO get matrix of instances and features: feature_raw
    feature_raw = np.array([[0]])
    # TODO get the directory path
    features_split_values = np.load('features_split_values.npy')

    bins_instance = []
    for feature_id in features:
        bins = features_split_values[feature_id]
        feature_values = [feature_raw[instance_id][feature_id]]
        distribution = get_feature_distribution(feature_values, bins)
        bins_instance.append(distribution)
    return jsonify({
        'bins_instance': bins_instance
    })

@app.route("/api/feature-importance", methods=["GET"])
def get_feature_importance():
    dataset_identifier = request.args["dataset"]
    dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
    return send_file(join(dataset_path, "feature_importance.bin"))

@app.route("/api/tree-size", methods=["GET"])
def get_tree_size():
    dataset_identifier = request.args["dataset"]
    dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
    return send_file(join(dataset_path, "tree_size.bin"))

@app.route('/api/manifest', methods=['GET'])
def get_manifest():
    dataset_identifier = request.args["dataset"]
    dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
    global warehouse
    if warehouse is None or warehouse.identifier is not dataset_identifier:
        warehouse = WareHouse(dataset_identifier, dataset_path)
    with open(join(dataset_path, "manifest")) as manifest_file:
        return manifest_file.read()

import time

@app.route('/api/feature-raw-zipped', methods=['GET'])
# @gzipped
def get_raw_feature_zipped():
    dataset_identifier = request.args["dataset"]
    dataset = dataset_identifier.split("-")[1]
    dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
    type = int(request.args["is_train"])
    if type:
        return send_file(join(dataset_path, "feature-raw.zip"))
    else:
        return send_file(join(dataset_path, "feature-raw-valid.zip"))


from flask import send_file

@app.route('/api/predicted-label', methods=['GET'])
def get_predicted_label():
    dataset_identifier = request.args["dataset"]
    type = int(request.args["is_train"])
    root = join(*[SERVER_ROOT, "result", dataset_identifier])
    l = np.loadtxt(join(root, "predicted-label-" + ("train" if type else "test")), dtype=np.int16)
    return jsonify(l.tolist())


@app.route('/api/posterior-by-class', methods=['GET'])
def get_posterior_by_class():
    start = time.time()
    dataset_identifier = request.args["dataset"]
    type = int(request.args["is_train"])
    class_ = request.args["class_"]
    root = join(*[SERVER_ROOT, "result", dataset_identifier])
    if type:
        dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier, "posteriors-train"])
    else:
        dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier, "posteriors-test"])
    return send_file(dataset_path + "-" + class_)

#add by Changjian, 2017/7/14
#load clustering result
@app.route('/api/clustering-by-class', methods=['GET'])
def get_clustering_by_class():
    start = time.time()
    dataset_identifier = request.args['dataset']
    type = int( request.args["is_train"])
    class_ = request.args["class_"]
    root = join(*[SERVER_ROOT, "result", dataset_identifier])
    if type:
        dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier, "clustering", "train"])
    else:
        dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier, "clustering", "test"])
    return send_file(dataset_path + "-" + class_)

#add by Changjian, 2017/7/14
@app.route('/api/perform-clustering-request', methods=['GET'])
def perform_clustering():
    dataset_identifier = request.args["dataset"]
    performClustering(dataset_identifier=dataset_identifier,label_number=9)
    return jsonify('[test]')

#add by Changjian, 2017/7/18
#for tree view
@app.route('/api/get-classifier-index', methods=['GET'])
def get_classifier():
    # app.logger.info(request.remote_addr + "\t" + request.url + "\t" + strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    dataset_identifier = request.args["dataset"]
    index = int(request.args["index"])
    # dataset_path = join(*[HTML_ROOT, "..", "result", dataset_identifier])
    # with open(join(dataset_path, "tree-shortened.json")) as json_file:
    #     all = json.loads(json_file.read())
    global TREE_ALL_DATA
    if dataset_identifier not in TREE_ALL_DATA:
        TREE_ALL_DATA = {}
        dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
        print(dataset_path)
        with open(join(dataset_path, "tree-shortened.json")) as json_file:
            TREE_ALL_DATA[dataset_identifier] = json.loads(json_file.read())
    all = TREE_ALL_DATA[dataset_identifier]
    return jsonify({
        "index": index,
        "tree": all[index]
    })

#add by Changjian, 2017/7/18
# for tree view
@app.route('/api/model-raw-index', methods=['GET'])
# @gzipped
def get_raw_model_iteration():
    # print(request.remote_addr + "\t" + request.url + "\t" + strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    dataset_identifier = request.args["dataset"]
    dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
    iteration = int(request.args["index"])
    with open(join(dataset_path, "model")) as model_file:
        in_block = False
        result = []
        for line in model_file:
            if line.startswith("Tree=" + str(iteration)):
                in_block = True
            if line.startswith("Tree=" + str(iteration + 1)):
                break
            if in_block:
                result.append(line)
        return "".join(result)

# add by Changjian, 2017/7/18
@app.route("/api/classifier-clustering-result", methods=['GET'])
def get_classifier_clustering_result():
    # print(request.remote_addr + "\t" + request.url + "\t" + strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    dataset_identifier = request.args["dataset"]
    dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
    if not exists(join(dataset_path, "cluster_result_all.json")):
        return ""
    with open(join(dataset_path, "cluster_result_all.json")) as result_file:
        return result_file.read()

# add by Changjian, 2017/7/18
@app.route('/api/get-classifiers-set', methods=['GET'])
def get_classifier_set():
    # print(request.remote_addr + "\t" + request.url + "\t" + strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    dataset_identifier = request.args["dataset"]
    # index = int(request.args["index"])
    index = [int(e) for e in request.args["index"].split("-")]
    dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
    # with open(join(dataset_path, "tree-shortened.json")) as json_file:
    #     all = json.loads(json_file.read())
    global TREE_ALL_DATA
    if dataset_identifier not in TREE_ALL_DATA:
        TREE_ALL_DATA = {}
        for key in TREE_ALL_DATA:
            del TREE_ALL_DATA[key]
        gc.collect()
        dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
        with open(join(dataset_path, "tree-shortened.json")) as json_file:
            TREE_ALL_DATA[dataset_identifier] = json.loads(json_file.read())
        print(dataset_identifier, "tree loaded")
    all = TREE_ALL_DATA[dataset_identifier]
    trees = []
    for i in index:
        trees.append(all[i])
    return jsonify({
        "index": index,
        "trees": trees
    })


# add by Changjian, 2017/7/18
@app.route('/api/model-raw-indices', methods=['GET'])
def get_raw_model_iterations():
    # print(request.remote_addr + "\t" + request.url + "\t" + strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    dataset_identifier = request.args["dataset"]
    dataset_path = join(*[SERVER_ROOT, "result", dataset_identifier])
    iterations = [int(e) for e in request.args["index"].split("-")]
    with open(join(dataset_path, "model")) as model_file:
        lines = model_file.readlines()
        results = []
        for iteration in iterations:
            in_block = False
            result = []
            for line in lines:
                if line.startswith("Tree=" + str(iteration)):
                    in_block = True
                if line.startswith("Tree=" + str(iteration + 1)):
                    break
                if in_block:
                    result.append(line)
            results.append("".join(result))
        return "|".join(results)

@app.route('/api/query-dataset', methods=['GET'])
def query_tag_names():
    datasets = listdir(join(SERVER_ROOT, "result"))
    return jsonify(datasets)

@app.route('/api/query-set-names', methods=['GET'])
def query_set_names():
    dataset_identifier = request.args["dataset"]
    manifest_path = join(SERVER_ROOT, "result", dataset_identifier, "manifest")
    if not exists(manifest_path):
        return jsonify({
            "message": "not exists",
            "status": "failure"
        })
    with open(manifest_path) as manifest_file:
        manifest = json.load(manifest_file)
        return jsonify({
            "status": "success",
            "set_names": manifest["set_names"]
        })

@app.route('/api/cluster-result', methods=['GET'])
def get_cluster_result():
    dataset_identifier = request.args["dataset"]
    setname = request.args["setname"]
    cluster_result_path = join(SERVER_ROOT, "result", dataset_identifier, "clustering_result_" + setname + ".json")
    return send_file(cluster_result_path)

if __name__ == '__main__':
    start = time.time()
    root = join(*[SERVER_ROOT, "result"])
    app.run(port=8083, host="0.0.0.0", threaded=True)
