import json
from datetime import datetime
from typing import List, Dict, Counter, Optional

import pandas as pd
import requests
from pydantic import BaseModel
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CONSUMPTION_URL = 'https://emdii-webtool.foxconn-na.com/api/getWO_PKGID?workorder='
SAP_REQUIREMENT = 'https://emdii-webtool.foxconn-na.com/api/get_wo_detail?workorder='


def parse_created_date(value: str) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.strptime(value.strip(), "%a, %d %b %Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def call_api(url, *, timeout=10, retries=3, backoff=0.5):
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))

    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout as e:
        raise RuntimeError(f"Request timed out after {timeout}s") from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error: {e.response.status_code}") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError("Request failed") from e
    except ValueError as e:
        raise RuntimeError("Invalid JSON response") from e


def summary_delivery(delivery_records: List[Dict[str, str]]) -> dict:
    # Read a json file

    # {
    #     "CREATED_DATE": "Thu, 18 Dec 2025 11:55:42 GMT",
    #     "EMP_NUMBER": "45654",
    #     "HH_PN": "T-KMV0000-G",
    #     "LINE_NAME": "SMTJ11",
    #     "MFR_PN": "PM1A112-11DA3-4H",
    #     "PKG_ID": "MPT0002506032956",
    #     "QTY": 50,
    #     "REMAIN_QTY": 0,
    #     "REMARKS": "WH ASIGNATION",
    #     "WO": "000390018996",
    #     "rowNum": 1
    # }
    # Create a report

    _consumptionByPN = {i["HH_PN"]: {"items": [], "qtys": []} for i in delivery_records}

    for i in delivery_records:
        _consumptionByPN[i["HH_PN"]]["qtys"].append(i["QTY"])
        _consumptionByPN[i["HH_PN"]]["items"].append(
            f'{i["CREATED_DATE"]}@{i["EMP_NUMBER"]}@{i["PKG_ID"]}@{i["QTY"]}@{i["LINE_NAME"]}')

    _return_summary = {}
    for pn, items in _consumptionByPN.items():
        _return_summary[pn] = {"reals": len(items["qtys"]), "qty": sum(items["qtys"]), "items": items["items"],
                               "std_pkg": Counter(items["qtys"]).most_common(1)[0][0]}

    # print(json.dumps(_return_summary, indent=4))
    # save to file
    # with open("summary_consumption.json", "w") as f:
    #     json.dump(_return_summary, f, indent=4)
    # for pn, qtys in _consumptionByPN.items():
    #     print(pn, sum(qtys))

    return _return_summary


class Material(BaseModel):
    high_level_pn: str
    part_number: str
    is_primary: bool
    request_qty: int
    description: str
    item: str
    updated_by: str
    last_modified: str


class DeliverMaterialList(BaseModel):
    pn: str
    reals: int
    qty: int
    std_pkg: int
    items: List[str]


class MaterialGroup(BaseModel):
    high_level_pn: str
    primary_pn: str
    request_qty: int
    consumption_qty: int
    attrition: int
    total_consumption: int
    total_deliver: int = 0
    overstock: int = 0
    over_deliver_rate: float = 0
    total_deliver_reals: int = 0
    std_pack: int = 0
    severity: float = 0
    sku: str
    wo: str
    materials: List[Material]
    deliver_materials: List[DeliverMaterialList] = []
    list_materials_str: List[str] = []


class MaterialGroupAndDeliversHandler(BaseModel):
    total_consumption: int = 0
    groups: List[MaterialGroup]

    def add_deliver_materials(self, data: dict):
        for group in self.groups:
            for material in group.materials:
                _temp = data.get(material.part_number)
                if _temp:
                    group.deliver_materials.append(
                        DeliverMaterialList(
                            pn=material.part_number,
                            reals=_temp["reals"],
                            qty=_temp["qty"],
                            std_pkg=_temp["std_pkg"],
                            items=_temp["items"]
                        )
                    )
            if len(group.deliver_materials) > 0:
                group.std_pack = max([item.std_pkg for item in group.deliver_materials])
            else: group.std_pack = 0

    def overstock_calculation(self):
        for group in self.groups:
            _deliver_total = sum([item.qty for item in group.deliver_materials])


            if group.std_pack > 0:
                # print(f"Total of groups without std packs: {group.high_level_pn} - {group.consumption_qty}")
                # print(_std_packs)
                # for item in group.deliver_materials:
                #     print(item.std_pkg)
                group.total_deliver_reals = sum([item.reals for item in group.deliver_materials])
                group.total_deliver = _deliver_total
                group.overstock = _deliver_total - group.total_consumption
                group.over_deliver_rate = (group.overstock / group.total_consumption)
                group.severity = group.overstock / group.std_pack

    def get_overstock_groups(self) -> List[MaterialGroup]:
        _result = ([element for element in self.groups if element.overstock > 0])
        # _result.sort(key= lambda x: x.overstock, reverse=True)
        # _result.sort(key=lambda x: x.total_deliver_reals, reverse=True)
        _result.sort(key=lambda x: x.severity, reverse=True)
        return _result

    def calculate_total_consumption(self):
        self.total_consumption = sum([item.total_consumption for item in self.groups])


def material_to_excel(material_groups: List[MaterialGroup]):
    df = pd.DataFrame(material_groups)
    df.to_excel("summary.xlsx", index=False)

def overdeliver_to_excel(material_groups: List[MaterialGroup], headers: tuple[str,str,str], creation_date, wo: str)-> tuple[int, int,List[dict]] :

    # Create a Summary
    _total_overdeliver_components = 0
    _total_overdeliver_reals = 0

    _temp = []
    for group in material_groups:
        if group.severity > 0:
            _total_overdeliver_components += group.overstock
            _total_overdeliver_reals += group.severity
        # print(group.severity)
        if group.severity > 1:
            _temp.append({
                "line":headers[0],
                "platform":headers[1],
                "sku": headers[2],
                "wo": group.wo,
                "created_date": creation_date,
                "high_level_pn": group.high_level_pn,
                "total_consumption": group.total_consumption,
                "total_deliver": group.total_deliver,
                "overstock": group.overstock,
                "severity": round(group.severity, 2),
            })
    _temp.sort(key=lambda x: x["severity"], reverse=True)
    # dfa = pd.DataFrame(_temp)
    # dfa.to_excel(f"reports/wo_{wo}_summary_severity.xlsx", index=False)

    # print(f"Total overdeliver components: {_total_overdeliver_components}")
    # print(f"Total overdeliver reals: {_total_overdeliver_reals}")

    return _total_overdeliver_components, _total_overdeliver_reals, _temp

    # df = pd.DataFrame(material_groups)
    # df.to_excel("summary.xlsx", index=False)

def format_requirement(wo: str):
    _responds = call_api(SAP_REQUIREMENT + wo)
    # Responds Data Structure
    # "COL_14": null,
    # "COL_15": "32024Q700-A0-5J42H",  high level part number
    # "COL_16": 0,
    # "COL_17": "1000", -> SLoc
    # "COL_18": null, -> primary part number
    # "COL_19": null,
    # "COL_20": null,
    # "COL_21": null,
    # "COL_22": null,
    # "COL_23": "47505", -> Updated by
    # "COL_24": "Fri, 08 Oct 2021 17:20:09 GMT", - last modified date
    # "CONTAINER_NO": null, -> if is phantom part number == x, phantom is high level part number id
    # "EMP_NO": "1",
    # "ERROR_FLAG": null,
    # "GROUP_NAME": 0, ->
    # "IN_STATION_TIME": "ST",
    # "LINE_NAME": "320253E00-279-H", -> part number
    # "MODEL_NAME": "0030", -> item
    # "NEXT_STATION": null,
    # "OUT_STATION_TIME": "MG3200",
    # "PALLET_NO": "IC,USB Power-Distribution Switches,APL35", -> material description
    # "SECTION_NAME": 0, -> requirement qty
    # "STATION_NAME": null,
    # "VERSION_CODE": "MX01", -> factory
    # "WORK_ORDER": "000390001893", -> wo
    if not _responds:
        print("No responds")
        return None

    _high_level_pn = []
    _materials = []
    _group_request_qty = []

    for item in _responds:
        if item["CONTAINER_NO"] == 'X':
            _high_level_pn.append({
                "high_level_pn": item["LINE_NAME"],
                "request_qty": int(item["SECTION_NAME"]),
                "consumption_qty": 0,
                "sku": item["COL_15"],
                "wo": item["WORK_ORDER"]
            })
            _group_request_qty.append(item["SECTION_NAME"])
        else:
            _materials.append({
                "high_level_pn": item["COL_15"],
                "part_number": item["LINE_NAME"],
                # "primary_pn": 'nan' if item["COL_18"] is None else item["COL_18"],
                "is_primary": True if item["MODEL_NAME"] == "0010" else False,
                "request_qty": int(item["SECTION_NAME"]),
                "description": item["PALLET_NO"],
                "item": item["MODEL_NAME"],
                "updated_by": item["COL_23"],
                "last_modified": item["COL_24"]
            })

    # Determine the PCB quantity by identifying the most frequently occurring value in _group_request_qty
    _total_pcb = Counter(_group_request_qty).most_common(1)[0][0]

    # Calculate the consumption quantity of each high-level part number
    for item in _high_level_pn:
        item["consumption_qty"] = item["request_qty"] / _total_pcb

    # Print the result
    # for item in _materials:
    #     print(json.dumps(item, indent=4))

    _high_level_pn_groups: List[MaterialGroup] = []
    for item in _high_level_pn:
        _high_level_pn_groups.append(
            MaterialGroup(
                high_level_pn=item['high_level_pn'],
                primary_pn="nan",
                request_qty=item['request_qty'],
                attrition=0,
                total_consumption=0,
                consumption_qty=int(item['consumption_qty']),
                sku=item['sku'],
                wo=item['wo'],
                materials=[]
            )
        )

    for item in _materials:
        for group in _high_level_pn_groups:
            if group.high_level_pn == item['high_level_pn']:
                group.materials.append(Material(**item))
                group.total_consumption += item['request_qty']

    # find primary pn
    for group in _high_level_pn_groups:
        group.attrition = group.total_consumption - group.request_qty
        for material in group.materials:
            group.list_materials_str.append(material.part_number)
            if material.is_primary:
                group.primary_pn = material.part_number

    #
    # for item in _high_level_pn_groups:
    #     print(json.dumps(item.model_dump(), indent=4))

    return _high_level_pn_groups


__total = []
__report = []

if __name__ == '__main__':



    # Read an Excel file

    wo_df = pd.read_excel("resources/work_order_list.xlsx")
    wo_df["start_date"] = pd.to_datetime(wo_df["Start Date"], errors="coerce")


    for idx, row in wo_df.iterrows():

        _wo = f"000{row['SAP_WO']}"

        _responds = call_api(CONSUMPTION_URL + _wo)

        if not _responds:
            print(f"no consumption {_wo}")
            continue

        _summary_deliver = summary_delivery(_responds)

        _material_group_handle = format_requirement(_wo)
        if not _material_group_handle:
            print(f"no sap {_wo}")
            continue



        print(f"start {_wo}")
        _handler = MaterialGroupAndDeliversHandler(groups=_material_group_handle)
        _handler.add_deliver_materials(_summary_deliver)
        _handler.overstock_calculation()
        _handler.calculate_total_consumption()
        # Save Json
        with open(f"reports/wo_{_wo}_materials_list.json", "w") as f:
            json.dump(_handler.model_dump(), f, indent=4)

        # for item in _handler.get_overstock_groups():
        #     print(json.dumps(item.model_dump(), indent=4))



        _t1, _t2, _data = overdeliver_to_excel(
            _handler.groups,
            (row['Line'], row['Platform'], row['Sku']),
            row['start_date'],
            _wo,
        )

        __total.append({
            "line": row['Line'],
            "platform": row['Platform'],
            "sku": row['Sku'],
            "start_date": row['start_date'],
            "wo": _wo,
            "total_overdeliver_components": _t1,
            "total_overdeliver_reals": _t2,
        })

        for item in _data:
            __report.append(item)

        print(f"finish {_wo}")



    # Create Excel Report
    df = pd.DataFrame(__report)
    with pd.ExcelWriter("reports/summary.xlsx", engine="openpyxl",
                        datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
        df.to_excel(writer, index=False)

    # Create Excel Report
    df = pd.DataFrame(__total)
    with pd.ExcelWriter("reports/totals.xlsx", engine="openpyxl",
                        datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
        df.to_excel(writer, index=False)

