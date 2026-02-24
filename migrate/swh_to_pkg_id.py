from collections import Counter

import requests

from cmd.smw_demand import POCKET_BASE_URL
from util.smw_stock import get_swh_inventory

POCKET_BASE_URL = "http://10.13.32.220:8090/api/collections/STD_PKG/records"


def swh_to_pkg_id():
    def most_common_number(nums):
        if not nums:
            return None  # or raise ValueError
        return Counter(nums).most_common(1)[0][0]

    inventory = get_swh_inventory()

    unique_pn = set(item.PN for item in inventory)

    pn_dict = {pn: [] for pn in unique_pn}

    for item in inventory:
        if item.PKG_ID[:2] in ["XR", "HL"]:
            continue
        pn_dict[item.PN].append(item.QTY)

    for pn, qtys in pn_dict.items():
        _mc = most_common_number(qtys)
        if not _mc:
            continue
        requests.post(POCKET_BASE_URL, json={"part_number": pn, "std_pkg": _mc})


    return None
