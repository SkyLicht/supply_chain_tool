import json
from typing import List
from pathlib import Path
import requests
from pydantic import BaseModel


class Material(BaseModel):
    primary_hh_pn: str
    track: str
    feeder_type: str
    description: str
    quantity: float
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


def as_number_or_zero(v):
    """Coerce possibly-None/empty/str numbers to float, defaulting to 0.0."""
    if v is None:
        return 0.0
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() in {"none", "nan", "null"}:
            return 0.0
        # Optional: normalize comma decimals like "12,5" -> "12.5"
        s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0

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
                        quantity=m.get("quantity"),  # <-- key part
                        feeder_type=m["feeder_type"],
                        alternates_hh_pn=m["alternates_hh_pn"]
                    ) for m in material_list if as_number_or_zero(m.get("quantity")) != 0
                ]
            )
        )
    # for ll in sheets:
    #     print(ll.model_dump(exclude_none=True))
    return LoadingList(sheets=sheets)


# Read json file
# def read_data(path: str):
#     with open(path) as f:
#         return json.load(f)



def read_data(path: str | Path):
    path = Path(path)
    # Try UTF-8 first (most common for JSON). Fallback to UTF-8 with BOM.
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except UnicodeDecodeError:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)


def upload_ll_to_pb(
        url:str,
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
    result = requests.post(f'{url}/api/collections/LOADING_LIST/records',
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


def create_material_in_pb(db_ip: str,sheet:str,id: str, category: str, ref: str, machine: str, side: str, record: Material):
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
        "sheet":sheet,
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
    result = requests.post(f"{db_ip}/api/collections/LOADING_LIST_PN/records", json=data)


def run_ll_upload(db_ip: str,path: str, ref: str , category: str = "SMT", ):
    # print(json.dumps(read_data(path), indent=4))

    param = ref.split("_")
    data = decompile_json(read_data(path))
    status = upload_ll_to_pb(url=db_ip,ref=ref, line=param[0], sku=param[1], rev=param[2],
                             smt=json.dumps(data.to_dict()["sheets"]), pth="[]")

    if status["status"] == 200:
        print(f"Upload success, id: {status['id']}")
        for sheet in data.sheets:
            for material in sheet.materials:
                pass

                create_material_in_pb(
                    db_ip,
                    sheet.header.sheet,
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
