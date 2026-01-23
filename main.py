import json
from collections import defaultdict
from gettext import find
from idlelib.search import find_again
from typing import List, Optional, Dict, Counter

import pandas as pd
from pydantic import BaseModel



class PartNumber(BaseModel):
    hh_pn: str
    customer_pn: str
    supplier_pn: str
    description: str
    supplier_name: str


class VPN(BaseModel):
    vpn: str  # vpn name
    item: float
    usage: int
    area: str
    locations: List[str]
    pn_list: List[PartNumber]

class BOM(BaseModel):
    HH_PCA_PN: str
    PCB_REV: str
    CUSTOMER: str
    BOM_REV: str
    PCA_REV: str
    PCA_DES: str
    CUSTOMER_PN: str
    DATE: str
    MODEL: str
    PLATFORM_NAME: str
    VPN_LIST: List[VPN]

class Material(BaseModel):
    material: str
    vpn: str
    description: str
    request_qty: float
    withdrawn_qty: float
    relevance: str
    usage: float
    area: str
    delivery_qty: float = 0



def format_bom(path: str):
    bom_details = pd.read_excel(path, engine="openpyxl", sheet_name="details")
    bom_data = pd.read_excel(path, engine="openpyxl", sheet_name="data")

    if bom_details.empty or bom_data.empty:
        raise ValueError("Empty DataFrame")

    # ['HH_PCA _PN', 'PCB_REV', 'CUSTOMER', 'BOM_REV', 'PCA_REV', 'PCA_DES',
    #  'CUSTOMER_PN', 'DATE', 'MODEL', 'PLATFORM_NAME']
    _bom_details = {
        "HH_PCA_PN": bom_details["HH_PCA_PN"][0],
        "PCB_REV": bom_details["PCB_REV"][0],
        "CUSTOMER": bom_details["CUSTOMER"][0],
        "BOM_REV": bom_details["BOM_REV"][0],
        "PCA_REV": bom_details["PCA_REV"][0],
        "PCA_DES": bom_details["PCA_DES"][0],
        "CUSTOMER_PN": bom_details["CUSTOMER_PN"][0],
        "DATE": bom_details["DATE"][0].to_pydatetime().strftime("%Y-%m-%d"),
        "MODEL": bom_details["MODEL"][0],
        "PLATFORM_NAME": bom_details["PLATFORM_NAME"][0],
    }

    def split_locations(locations: Optional[object]) -> List[str]:
        # Handle None, NaN, and empty strings
        if locations is None:
            return []
        if pd.isna(locations):
            return []

        # Force to string (in case it's numeric), then split
        s = str(locations).strip()
        if not s:
            return []

        return [x.strip() for x in s.split(",") if x.strip()]

    def is_blank(cell: Optional[object]) -> bool:
        return pd.isna(cell)

    _vpn_area_list = {}
    _vpn_list: List[VPN] = []
    _temp_vpn: VPN | None = None
    for row in bom_data.itertuples(index=False):
        # print(row)
        if row[0] > 0:
            if _temp_vpn is not None:
                _vpn_list.append(_temp_vpn)
            _temp_vpn = VPN(
                vpn='nan' if is_blank(row[1]) else row[1],
                item=row[0],
                usage=0 if is_blank(row[7]) else row[7],
                area=row[9],
                locations=split_locations(row[8]),
                pn_list=[])
            _temp_vpn.pn_list.append(
                PartNumber(
                    hh_pn=row[2],
                    customer_pn=row[3],
                    supplier_pn=row[6],
                    description=row[4],
                    supplier_name=row[5]
                )
            )

            _vpn_area_list['nan' if is_blank(row[1]) else row[1]] = row[9]
        else:
            _temp_vpn.pn_list.append(
                PartNumber(
                    hh_pn=row[2],
                    customer_pn=row[3],
                    supplier_pn=row[6],
                    description=row[4],
                    supplier_name=row[5]
                )
            )

    _boom = {
        "vpn_areas": _vpn_area_list,
        **_bom_details,
        "VPN_LIST": [item.model_dump(exclude_none=True) for item in _vpn_list],
    }
    # for i in _vpn_list:
    #     print(json.dumps(i.model_dump(exclude_none=True), indent=4))

    # print(json.dumps(_boom, indent=4))

    # save to file

    with open("bom.json", "w") as f:
        json.dump(_boom, f, indent=4)

    # print(BOM_DETAILS.columns)
    # print(BOM_DETAILS["HH_PCA_PN"][0])


class Materials(BaseModel):
    plant: str = ""
    order: str = ""
    sku: str = ""

    materials: List[Material]
    smt: List[Material] = []
    pth: List[Material] = []

    details: dict = {}

    def print_materials(self):
        for i in self.materials:
            print(i)

    def join_delivery(self, delivery_materials: List[dict]):
        # delivery_materials = []
        # {
        #     "pn": "T-KMV0000-G",
        #     "reals": 120,
        #     "qty": 6915
        # },
        for material in self.materials:
            material.delivery_qty = _find_material = sum(i["qty"] for i in delivery_materials if material.material == i["pn"])



    def sort_material(self):
        for i in self.materials:
            if i.material.startswith("smt"):
                self.smt.append(i)
            else:
                self.pth.append(i)

    def create_detail(self, total_units=0):
        grouped: Dict[str, List[Material]] = defaultdict(list)

        for m in self.materials:
            grouped[m.vpn].append(m)

        _summary_vpn = []

        for vpn, materials in grouped.items():
            _summary_vpn.append({
                "vpn": vpn,
                "qty": sum(m.request_qty for m in materials),
                "area": materials[0].area,
                "usage": next((m.usage for m in materials if m.usage > 0), 0),
                "part_numbers": sum(1 for m in materials if m.request_qty > 0),
                "delivery_qty": sum(m.delivery_qty for m in materials)
            })

        _summary_vpn.sort(key=lambda x: x["area"], reverse=True)

        for i in _summary_vpn:
            _attrition = i["qty"] - (total_units * i["usage"])
            i["attrition"] = _attrition
            i["overissue"] = i["delivery_qty"] - i["qty"]
            i["over_deliver"] = i["delivery_qty"] / i["qty"] if i["qty"] > 0 else 0


        # Save to excel
        df = pd.DataFrame(_summary_vpn)
        df.to_excel("summary.xlsx", index=False)





def format_requirement(path: str, bom_areas_path: str,deliver_path: str, total_units: int = 0):
    # Read a json file
    with open(bom_areas_path, "r") as f:
        bom_areas = json.load(f)

    _requirement = pd.read_excel(path, engine="openpyxl")

    if _requirement.empty:
        raise ValueError("Empty DataFrame")

    _materials: Materials = Materials(materials=[])
    for i in _requirement.itertuples(index=False):
        _materials.materials.append(
            Material(
                material=i[3],
                vpn=i[5],
                description=i[4],
                request_qty=i[7],
                withdrawn_qty=i[8],
                relevance=i[21],
                usage=i[22],
                area=bom_areas['vpn_areas'][i[5]]
            )
        )

    _materials.sort_material()
    _materials.join_delivery(json.load(open(deliver_path)))
    # _materials.print_materials()
    _materials.create_detail(total_units=total_units)


def summary_delivery(path: str):
    # Read a json file
    with open(path, "r") as f:
        consumption = json.load(f)
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

    _consumptionByPN = {i["HH_PN"]: {"pkg": [], "qtys":[]} for i in consumption}

    for i in consumption:
        _consumptionByPN[i["HH_PN"]]["qtys"].append(i["QTY"])
        _consumptionByPN[i["HH_PN"]]["pkg"].append(i["PKG_ID"])

    _return_summary = []
    for pn, items in _consumptionByPN.items():
        _return_summary.append({"pn": pn, "reals": len(items["qtys"]), "qty": sum(items["qtys"]), "pkgs": items["pkg"], "std_pkg": Counter(items["qtys"]).most_common(1)[0][0]})

    # save to file
    with open("summary_consumption.json", "w") as f:
        json.dump(_return_summary, f, indent=4)
    # for pn, qtys in _consumptionByPN.items():
    #     print(pn, sum(qtys))


def find_pn_in_deliver(path:str, pn: List[str]):
    with open(path, "r") as f:
        deliver = json.load(f)

    _temp = []
    for item in deliver:
        if item["HH_PN"] in pn:
            _temp.append(item)

    _df = pd.DataFrame(_temp)
    _df["CREATED_DATE"] = pd.to_datetime(_df["CREATED_DATE"])

    _df.sort_values("CREATED_DATE", inplace=True)

    _df.reset_index(inplace=True, drop=True)
    _df.to_excel("pn_in.xlsx", index=False)
    # to excel




# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # format_bom(r"C:\Users\skyli\Downloads\M15KP_BOOM.xlsx")
    # summary_delivery(r"C:\Users\jorgeortiza\OneDrive - Foxconn\IE\Materials\Consumption\wo_000390018996.json")
    # format_requirement(r"C:\Users\skyli\Downloads\EXPORT_20260117204312.xlsx", 'bom.json',"summary_consumption.json", 6000)
    find_pn_in_deliver(r"C:\Users\jorgeortiza\OneDrive - Foxconn\IE\Materials\Consumption\wo_000390018996.json", ['62010JC00-011-H'])
