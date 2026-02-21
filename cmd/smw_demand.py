import json
from typing import List, Dict

import requests
from pydantic import BaseModel

from util.smw_stock import get_swh_inventory
from util.wo_details import get_wo_details, MaterialGroup

POCKET_BASE_URL = 'http://10.13.32.220:8090'


class MOStatus(BaseModel):
    id: str
    mo: str
    line: str
    sku: str
    ver: str
    target_qty: int
    input_qty: int
    output_qty: int


def step_1()-> list[MOStatus] | None:
    # http://10.13.32.220:8090/api/collections/WO_STATUS/records
    # "BIOS_REV": "1.31.1",
    # "DEFAULT_LINE": "J05",
    # "EMP_NO": "44971",
    # "EOL": false,
    # "INPUT_COMPLETION": 0.18914285714285714,
    # "INPUT_QTY": 662,
    # "IS_COMPLETED": false,
    # "IS_RUNNING": true,
    # "LAST_TIME_RUNNING": "Fri Feb 20 2026 08:31:03 GMT-0700 (MST)",
    # "MODEL_NAME": "MM7WY",
    # "MO_CREATE_DATE": "Thu, 19 Feb 2026 21:26:34 GMT",
    # "MO_NUMBER": "000390019380",
    # "MO_SCHEDULE_DATE": "Mon, 23 Feb 2026 12:00:00 GMT",
    # "NOT_INPUT": false,
    # "OUTPUT_QTY": 274,
    # "STATUS": "nan",
    # "TARGET_QTY": 3500,
    # "TOTAL_SCRAP_QTY": 0,
    # "VERSION_CODE": "A00",
    # "collectionId": "pbc_2332791983",
    # "collectionName": "WO_STATUS",
    # "created": "2026-02-12 21:51:00.148Z",
    # "id": "qej2hhruys09abb",
    # "updated": "2026-02-20 15:31:03.738Z"

    data: list[MOStatus] = []
    call = requests.get(f'{POCKET_BASE_URL}/api/collections/WO_STATUS/records?filter=(IS_RUNNING = true)')

    if call.status_code != 200:
        return None

    for records in call.json().get('items'):
        if records.get('DEFAULT_LINE') in ['J01', 'J02', 'J03', 'J05', 'J06', 'J08']:
            data.append(
                MOStatus(
                    id=records.get('id'),
                    mo=records.get('MO_NUMBER'),
                    line=records.get('DEFAULT_LINE'),
                    sku=records.get('MODEL_NAME'),
                    ver=records.get('VERSION_CODE'),
                    target_qty=records.get('TARGET_QTY'),
                    input_qty=records.get('INPUT_QTY'),
                    output_qty=records.get('OUTPUT_QTY'))
            )

    return data


def step_2(data: list[MOStatus]) -> Dict[str, List[MaterialGroup]]:

    wo_list: Dict[str, List[MaterialGroup]] = {}


    for record in data:
        pcb_pending_qty: int = record.target_qty - record.output_qty
        wo_details = get_wo_details(record.mo)

        for group in wo_details:
            _left = group.consumption_qty * pcb_pending_qty
            group.pending_consumption = _left
        wo_list[record.mo] = wo_details
    return wo_list

def step_3()->Dict[str, float]:
    inventory = get_swh_inventory()
    summary: Dict[str, float] = {}

    for item in inventory:
        if not item.PN:
            continue
        qty = float(item.QTY or 0)
        summary[item.PN] = summary.get(item.PN, 0) + qty

    return summary

def apply_pending_consumption(
    inventory: Dict[str, float],
    wo_list: Dict[str, List[MaterialGroup]],
) -> Dict[str, float]:
    for key, wo in wo_list.items():
        for group in wo:
            if group.pending_consumption == 0 or group.request_qty <= 0:
                continue
            for material in group.materials:
                if material.request_qty > 0:
                    pending_for_material = group.pending_consumption * (
                        material.request_qty / group.request_qty
                    )
                    current = inventory.get(material.part_number)
                    if current is None:
                        inventory[material.part_number] = -pending_for_material
                    else:
                        inventory[material.part_number] = current - pending_for_material
    return inventory

def ana_main():
    mo = step_1()
    if mo is None:
        return

    wo_list = step_2(mo)
    summary = step_3()
    adjusted = apply_pending_consumption(summary, wo_list)
    adjusted = sorted(adjusted.items(), key=lambda x: x[1], reverse=True)
    print(json.dumps(adjusted, indent=2))

