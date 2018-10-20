from epanet_file_repair import EpanetFileRepair

if __name__ == '__main__':
    efr = EpanetFileRepair()
    efr.filepath = 'your path to file'
    efr.savepath = 'your result path to file'
    efr.show_results = True
    efr.remove_not_connected_nodes = True
    # to define start nodes, write them in array e.g. ['16', '1398']
    # otherwise all tanks and reservoirs will be the starting nodes
    efr.check_everything()
