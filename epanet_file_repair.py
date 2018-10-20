import functools
from enum import Enum
from typing import List, Iterable
import networkx as nx
import re


class Result(object):
    def __init__(self, error_info: str, success_info: str):
        self.error_info = error_info
        self.success_info = success_info

    def __call__(self, wrapped_function):
        @functools.wraps(wrapped_function)
        def show_results(f, *args, **kwargs):
            x = wrapped_function(f, *args, **kwargs)
            if not f.show_results:
                return x
            temp = ''
            if EpanetFileRepair.Parameters.Nodes.value == args[0]:
                temp = 'NODES:'
            elif EpanetFileRepair.Parameters.Links.value == args[0]:
                temp = 'LINKS:'
            if f.errors:
                print('{}{}: {}'.format(temp, self.error_info, f.errors))
            elif not f.errors:
                print('{}{}'.format(temp, self.success_info))
            return x
        return show_results


class EpanetFileRepair(object):
    class Parameters(Enum):
        Nodes = ["[JUNCTIONS]", "[TANKS]", "[RESERVOIRS]"]
        Links = ["[PIPES]", "[PUMPS]", "[VALVES]"]
        Other = ["[COORDINATES"]

    def __init__(self):
        self.__file_path = None
        self.__save_path = 'result.inp'
        self.__remove_not_connected = False
        self.__errors = None
        self.__show_results = True
        self.__found_nodes = None
        self.__unconnected_nodes = None
        self.__start_nodes = set()
        self.__g = None

    @property
    def errors(self):
        return self.__errors

    @property
    def start_nodes(self):
        return self.__start_nodes

    @property
    def unconnected_nodes(self):
        return self.__unconnected_nodes

    @property
    def found_nodes(self):
        return self.__found_nodes

    @property
    def filepath(self):
        return self.__file_path

    @filepath.setter
    def filepath(self, x: str):
        self.__file_path = x

    @property
    def savepath(self):
        return self.__save_path

    @savepath.setter
    def savepath(self, x: str):
        self.__save_path = x

    @property
    def remove_not_connected_nodes(self):
        return self.__remove_not_connected

    @remove_not_connected_nodes.setter
    def remove_not_connected_nodes(self, x: bool):
        self.__remove_not_connected = x

    @property
    def show_results(self):
        return self.__show_results

    @show_results.setter
    def show_results(self, x: bool):
        self.__show_results = x

    def __clean(self):
        self.__errors = None
        self.__found_nodes = None
        self.__unconnected_nodes = None
        self.__g = None

    @Result('Duplicates were found', 'No duplicates were found')
    def check_duplicates(self, elements: List):
        self.__clean()
        dictionary = dict()
        for line in self._read_file(elements):
            node_id = line.split("\t")[0]
            dictionary[node_id] = dictionary.get(node_id, 0) + 1
        if all(value == 1 for value in dictionary.values()):
            return True
        self.__errors = [key for key, value in dictionary.items() if value > 1]
        return False

    def check_network(self, start_nodes: Iterable = None, save_path: str = None):
        self._build_graph(start_nodes)

        if self.__remove_not_connected:
            self._remove_nodes_from_file(self.__errors, save_path)

    @Result('Unconnected nodes', '')
    def _build_graph(self, start_nodes: Iterable = None):
        self.__clean()
        self.__g = nx.Graph()

        all_nodes = set()

        for line in self._read_file(EpanetFileRepair.Parameters.Nodes.value):
            node_id = line.split(" ")[0]
            self.__g.add_node(node_id)
            all_nodes.add(node_id)

        for line in self._read_file(EpanetFileRepair.Parameters.Links.value):
            node_1 = line.split(" ")[1]
            node_2 = line.split(" ")[2]
            self.__g.add_edge(node_1, node_2)

        if not start_nodes:
            self.find_tanks_and_reservoirs()
            if not self.__start_nodes:
                raise ValueError('Start nodes must be declared')
        else:
            self.__start_nodes = start_nodes

        nodes = set()
        for node in self.__start_nodes:
            if type(node) is not str:
                node = str(node)
            nodes = nodes.union(set(nx.dfs_postorder_nodes(self.__g, node)))

        self.__found_nodes = nodes
        self.__errors = [node for node in all_nodes if node not in self.__found_nodes]

    def find_tanks_and_reservoirs(self):
        for line in self._read_file([EpanetFileRepair.Parameters.Nodes.value[1],
                                     EpanetFileRepair.Parameters.Nodes.value[2]]):
            self.__start_nodes.add(line.split(" ")[1])

    @Result('', 'Unconnected nodes removed')
    def _remove_nodes_from_file(self, remove_nodes: Iterable, save_path: str = None):
        nodes = False
        links = False
        first = False

        if not save_path:
            save_path = self.__save_path

        with open(self.__file_path, 'r') as f:
            with open(save_path, 'w') as output:
                for l in f:
                    line = re.sub('\s+', ' ', l).strip()
                    if EpanetFileRepair.Parameters.Nodes.value[0] in line \
                            or EpanetFileRepair.Parameters.Nodes.value[1] in line \
                            or EpanetFileRepair.Parameters.Nodes.value[2] in line \
                            or EpanetFileRepair.Parameters.Other.value[0] in line:
                        nodes = True
                        first = True
                        links = False
                    elif EpanetFileRepair.Parameters.Links.value[0] in line \
                            or EpanetFileRepair.Parameters.Links.value[1] in line \
                            or EpanetFileRepair.Parameters.Links.value[2] in line:
                        nodes = False
                        first = True
                        links = True
                    elif '[' in line:
                        nodes = False
                        links = False
                    elif ';' in line[:1] or not line:
                        first = True
                    if not (nodes and not first and line.split(" ")[0] not in remove_nodes) \
                            and not (links and not first and (line.split(" ")[1] not in remove_nodes or
                                                              line.split(" ")[2] not in remove_nodes)):
                        output.write(l)
                    first = False

        self.__errors = None

    def check_everything(self, start_node: Iterable = None):
        self.check_duplicates(EpanetFileRepair.Parameters.Nodes.value)
        self.check_duplicates(EpanetFileRepair.Parameters.Links.value)
        self.check_network(start_node)

    def _read_file(self, arr: List):
        check = False
        first = False
        with open(self.__file_path, 'r') as f:
            for l in f:
                line = re.sub('\s+', ' ', l).strip()
                while len(arr) < 3:
                    arr.append('[]')
                if arr[0] in line or arr[1] in line or arr[2] in line:
                    check = True
                    first = True
                elif '[' in line:
                    check = False
                elif ';' in line[:1] or not line:
                    first = True
                if check and not first:
                    yield line
                first = False
