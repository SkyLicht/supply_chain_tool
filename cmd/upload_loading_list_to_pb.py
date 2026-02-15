import json
from typing import List

import requests
from pydantic import BaseModel


class Material(BaseModel):
    primary_hh_pn: str
    track: str
    feeder_type: str
    description: str
    quantity: int
    location: str
    alternates_hh_pn: List[str] = []


class Header(BaseModel):
    line: str
    sheet: str
    rev: str
    board_side: str
    machine: str


class Sheet(BaseModel):
    id: str
    header: Header
    materials: List[Material]


class LoadingList(BaseModel):
    sheets: List[Sheet] = []

    def to_dict(self):
        return self.model_dump()


def decompile_json(data: dict) -> LoadingList:
    sheets: List[Sheet] = []
    for records in data:
        header = records["header"]
        material_list = records["materials"]

        sheets.append(
            Sheet(
                id=records["id"],
                header=Header(
                    line=header["line"],
                    sheet=header["sheet"],
                    rev=header["rev"],
                    board_side=header["board_side"],
                    machine=header["machine"],
                ),
                materials=[
                    Material(
                        primary_hh_pn=m["primary_hh_pn"],
                        track=m["track"],
                        location=m["location"],
                        description=m["parts_type"],
                        quantity=m["quantity"],
                        feeder_type=m["feeder_type"],
                        alternates_hh_pn=m["alternates_hh_pn"]
                    ) for m in material_list
                ]
            )
        )
    # for ll in sheets:
    #     print(ll.model_dump(exclude_none=True))
    return LoadingList(sheets=sheets)


# Read json file
def read_data(path: str):
    with open(path) as f:
        return json.load(f)


def upload_ll_to_pb(
        ref: str,
        line: str,
        sku: str,
        rev: str,
        smt: str,
        pth: str
):
    # /api/collections/LOADING_LIST/records
    # data = {
    #     "ref": "test",
    #     "line": "test",
    #     "sku": "test",
    #     "smt": "JSON",
    #     "pth": "JSON"
    # };
    result = requests.post("http://192.168.0.85:8090/api/collections/LOADING_LIST/records",
                           json=dict(ref=ref, line=line, sku=sku, rev=rev, smt=smt, pth=pth))

    if result.status_code == 200:
        return {
            "status": 200,
            "id": result.json()["id"]

        }
    else:
        return {
            "status": result.status_code,
            "message": result.json()["message"],
            "data": result.json()["data"]
        }


def create_material_in_pb(id: str, category: str, ref: str, machine: str, side: str, record: Material):
    # http://192.168.0.85:8090
    # api/collections/LOADING_LIST_PN/records
    # data = {
    #     "ref": "test",
    #     "machine": "test",
    #     "side": "test",
    #     "track": "test",
    #     "part_number": "test",
    #     "feeder_type": "test",
    #     "loading_list": "RELATION_RECORD_ID",
    #     "category": "SMT",
    #     "qty": 123,
    #     "alternates_pn": "JSON"
    # };

    data = {
        "ref": ref,
        "machine": machine,
        "side": side,
        "track": record.track,
        "part_number": record.primary_hh_pn,
        "loading_list": id,
        "qty": record.quantity,
        "alternates_pn": json.dumps(record.alternates_hh_pn),
        "feeder_type": record.feeder_type,
        "category": category
    }
    result = requests.post("http://192.168.0.85:8090/api/collections/LOADING_LIST_PN/records", json=data)


def run_ll_upload(path: str, ref: str , category: str = "SMT", ):
    # print(json.dumps(read_data(path), indent=4))

    param = ref.split("_")
    data = decompile_json(read_data(path))
    status = upload_ll_to_pb(ref=ref, line=param[0], sku=param[1], rev=param[2],
                             smt=json.dumps(data.to_dict()["sheets"]), pth="[]")

    if status["status"] == 200:
        print(f"Upload success, id: {status['id']}")
        for sheet in data.sheets:
            for material in sheet.materials:
                pass

                create_material_in_pb(
                    id=status["id"],
                    category=category,
                    ref=ref,
                    machine=sheet.header.machine,
                    side=sheet.header.board_side,
                    record=material
                )
    else:
        print(f"Upload failed, status: {status['status']}, message: {status['message']}" +
              f"\ndata: {status['data']}")
